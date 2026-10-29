"""Ads funding paid straight into a Meta ads invoice through Paystack.

The agent asks for an amount only; the desk approves (nothing is paid); the
agent then gives the Meta invoice and presses Pay; Paystack confirms the
account is Meta's and pays it at once; only then is the loan owed.
"""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.partners import paystack_transfers as paystack
from apps.partners.loan_payouts import resend_low_balance
from apps.partners.models import AgentProfile, Loan, Wallet
from apps.partners.payouts import LOW_BALANCE_NOTE

KEY = "sk_test_simulated"
P = "apps.partners.paystack_transfers"
ADS_LINK = "https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=290226488340854"
NOT_FOUND = paystack.PaystackRejected("Transfer not found")


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=True)
class MetaInvoiceLoanTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="agent@example.com", full_name="Ada Agent", role=User.Role.AGENT, country="Nigeria"
        )
        self.agent = AgentProfile.objects.create(user=self.user)
        self.wallet = Wallet.objects.create(agent=self.agent, currency="NGN")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.resolve = mock.patch(f"{P}.resolve_account", return_value="Meta Ads").start()
        mock.patch(f"{P}.bank_name_for", return_value="OPay").start()
        mock.patch(f"{P}.create_recipient", return_value="RCP_meta").start()
        self.verify = mock.patch(f"{P}.verify_transfer", side_effect=NOT_FOUND).start()
        self.addCleanup(mock.patch.stopall)

    def request_loan(self, **overrides):
        body = {"requested_amount": "10000", "purpose": "Facebook Ads", **overrides}
        return self.client.post("/api/partners/loans/", body, format="json")

    def pay(self, loan, **overrides):
        body = {
            "ad_account_link": ADS_LINK,
            "meta_bank_code": "999992",
            "meta_account_number": "5624424318",
            **overrides,
        }
        return self.client.post(f"/api/partners/loans/{loan.pk}/pay-meta/", body, format="json")

    def owed(self):
        return Wallet.objects.get(pk=self.wallet.pk).loan_balance

    def approve(self, loan):
        staff = User.objects.filter(email="approver@example.com").first() or User.objects.create_superuser(
            email="approver@example.com", password="pw-123456"
        )
        desk = APIClient()
        desk.force_login(staff)
        desk.post(reverse("admin:partners_loan_changelist"), {"action": "action_approve_and_pay_meta", "_selected_action": [loan.pk]})
        loan.refresh_from_db()
        return loan

    def approved_loan(self):
        self.assertEqual(self.request_loan().status_code, 201)
        return self.approve(Loan.objects.get())

    # ── The request: an amount only ──────────────────────────────────

    def test_a_request_needs_only_an_amount_and_goes_to_the_desk(self):
        response = self.request_loan()
        self.assertEqual(response.status_code, 201, response.content)
        loan = Loan.objects.get()
        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertFalse(loan.pays_meta)
        self.resolve.assert_not_called()
        self.assertEqual(self.owed(), Decimal("0"))
        self.assertTrue(self.client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])

    def test_invoice_details_sent_with_the_request_are_ignored(self):
        self.request_loan(meta_bank_code="999992", meta_account_number="1234567890")
        self.assertFalse(Loan.objects.get().pays_meta)

    # ── The desk approves: nothing is paid, the agent is emailed ──────

    def test_approval_pays_nothing_and_emails_the_agent(self):
        send = mock.patch(f"{P}.send_transfer").start()
        email = mock.patch("apps.accounts.emails.send_loan_ready_for_invoice_email").start()
        with self.captureOnCommitCallbacks(execute=True):
            loan = self.approved_loan()
        send.assert_not_called()
        self.assertEqual(loan.status, Loan.Status.APPROVED)
        self.assertEqual(loan.approved_amount, Decimal("10000"))
        self.assertTrue(loan.paystack_reference.startswith("gabstep-ln-"))
        self.assertTrue(loan.awaiting_invoice)
        self.assertEqual(self.owed(), Decimal("0"))
        self.assertTrue(self.client.get("/api/partners/loans/").json()[0]["awaiting_invoice"])
        email.assert_called_once()

    def test_a_request_cannot_be_paid_before_approval(self):
        self.request_loan()
        send = mock.patch(f"{P}.send_transfer").start()
        self.assertEqual(self.pay(Loan.objects.get()).status_code, 400)
        send.assert_not_called()

    # ── The agent gives the invoice and presses Pay ──────────────────

    def test_pay_sends_meta_the_approved_amount_and_only_then_is_it_owed(self):
        loan = self.approved_loan()
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success", "transfer_code": "TRF_1"}).start()
        response = self.pay(loan)
        self.assertEqual(response.status_code, 200, response.content)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.DISBURSED)
        self.assertEqual((loan.meta_account_name, loan.meta_bank_name, loan.meta_account_number), ("Meta Ads", "OPay", "5624424318"))
        amount, recipient, reference, _reason = send.call_args[0]
        self.assertEqual((amount, recipient, reference), (Decimal("10000.00"), "RCP_meta", loan.paystack_reference))
        self.assertEqual(self.owed(), Decimal("10000"))
        # Pressing Pay again pays nothing more.
        self.assertEqual(self.pay(loan).status_code, 400)
        send.assert_called_once()

    def test_an_account_that_is_not_metas_is_refused(self):
        loan = self.approved_loan()
        self.resolve.return_value = "John Doe"
        send = mock.patch(f"{P}.send_transfer").start()
        response = self.pay(loan)
        self.assertEqual(response.status_code, 400)
        self.assertIn("not Meta", str(response.json()))
        send.assert_not_called()
        loan.refresh_from_db()
        self.assertEqual((loan.status, loan.meta_account_number), (Loan.Status.APPROVED, ""))

    def test_the_link_must_be_facebook_ads_manager(self):
        loan = self.approved_loan()
        send = mock.patch(f"{P}.send_transfer").start()
        for link in ("https://example.com/adsmanager?act=123", "https://business.facebook.com/adsmanager",
                     "https://facebook.com.evil.com/?act=1", "javascript://facebook.com/?act=1"):
            self.assertEqual(self.pay(loan, ad_account_link=link).status_code, 400, link)
        send.assert_not_called()

    def test_another_agent_cannot_pay_this_loan(self):
        loan = self.approved_loan()
        other = User.objects.create_user(email="other@example.com", role=User.Role.AGENT, country="Nigeria")
        Wallet.objects.create(agent=AgentProfile.objects.create(user=other), currency="NGN")
        self.client.force_authenticate(other)
        send = mock.patch(f"{P}.send_transfer").start()
        self.assertEqual(self.pay(loan).status_code, 404)
        send.assert_not_called()

    def test_a_low_paystack_balance_holds_it_and_sends_it_once_later(self):
        loan = self.approved_loan()
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Your balance is not enough")).start()
        self.pay(loan)
        loan.refresh_from_db()
        self.assertEqual((loan.status, loan.review_reason), (Loan.Status.APPROVED, LOW_BALANCE_NOTE))
        self.assertFalse(loan.awaiting_invoice)  # sent again by itself, not by the agent
        self.assertEqual(self.owed(), Decimal("0"))
        reference = loan.paystack_reference
        Loan.objects.filter(pk=loan.pk).update(sent_at=timezone.now() - timedelta(hours=1))

        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        resend_low_balance()
        resend_low_balance()
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.DISBURSED)
        send.assert_called_once()
        self.assertEqual(send.call_args[0][2], reference)
        self.assertEqual(self.owed(), Decimal("10000"))

    def test_a_refused_payment_lets_the_agent_give_a_new_invoice(self):
        loan = self.approved_loan()
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Invalid account")).start()
        self.pay(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.APPROVED)
        self.assertTrue(loan.awaiting_invoice)
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        self.assertEqual(self.pay(loan, meta_account_number="8012345678").status_code, 200)
        loan.refresh_from_db()
        self.assertEqual((loan.status, loan.meta_account_number), (Loan.Status.DISBURSED, "8012345678"))
        self.assertEqual(send.call_args[0][2], loan.paystack_reference)

    def test_a_failed_payment_to_meta_is_not_owed_and_a_new_request_is_allowed(self):
        loan = self.approved_loan()
        mock.patch(f"{P}.send_transfer", return_value={"status": "failed"}).start()
        self.pay(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.FAILED)
        self.assertEqual(self.owed(), Decimal("0"))
        self.assertEqual(self.request_loan().status_code, 201)

    def test_a_reversal_after_payment_removes_what_was_owed(self):
        from apps.partners.loan_payouts import apply_status

        loan = self.approved_loan()
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        self.pay(loan)
        loan.refresh_from_db()
        self.assertEqual(self.owed(), Decimal("10000"))
        apply_status(loan, {"status": "reversed"})
        apply_status(loan, {"status": "reversed"})  # a repeat changes nothing
        loan.refresh_from_db()
        self.assertEqual((loan.status, self.owed()), (Loan.Status.FAILED, Decimal("0")))

    def test_the_staff_disburse_action_never_touches_an_approved_meta_loan(self):
        loan = self.approved_loan()
        staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        desk = APIClient()
        desk.force_login(staff)
        with mock.patch("apps.partners.admin.send_loan_approved_email"):
            desk.post(reverse("admin:partners_loan_changelist"), {"action": "action_approve_and_disburse", "_selected_action": [loan.pk]})
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.APPROVED)
        self.assertEqual(self.owed(), Decimal("0"))

    # ── Outside Nigeria: as before ─────────────────────────────────────

    def test_an_agent_outside_nigeria_keeps_the_staff_flow(self):
        User.objects.filter(pk=self.user.pk).update(country="Ghana")
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))
        response = self.client.post(
            "/api/partners/loans/", {"requested_amount": "10000", "purpose": "Facebook Ads"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        loan = self.approve(Loan.objects.get())
        self.assertEqual(loan.status, Loan.Status.PENDING)  # Meta approval skips it
        self.assertFalse(loan.pays_meta)
        self.resolve.assert_not_called()


class MetaAccountNameTests(TestCase):
    """Only names that really are Meta's pass; look-alikes do not."""

    def test_meta_names_from_any_bank_pass(self):
        from apps.partners.loan_payouts import is_meta_account_name

        for name in ("Meta Ads", "META ADS", "Meta Platforms Ireland Ltd", "Facebook Ads", "FACEBOOK",
                     "EBANX / Meta Ads", "Ebanx-Facebook"):
            self.assertTrue(is_meta_account_name(name), name)

    def test_look_alike_names_fail(self):
        from apps.partners.loan_payouts import is_meta_account_name

        for name in ("Metallic Ventures", "John Meta", "EMETA LTD", "Ametalo Meta Stores", "Metaverse Nig Ltd",
                     "Faceboook Ads", "EBANX Payments", "", "John Doe"):
            self.assertFalse(is_meta_account_name(name), name)

    @override_settings(META_ACCOUNT_NAMES="Meta Collections Ltd, Instagram Ads")
    def test_names_the_desk_adds_are_accepted_exactly(self):
        from apps.partners.loan_payouts import is_meta_account_name

        self.assertTrue(is_meta_account_name("META COLLECTIONS LTD"))
        self.assertTrue(is_meta_account_name("Instagram Ads"))
        self.assertFalse(is_meta_account_name("Instagram Ads Agency"))


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=True)
class MetaInvoiceAtAnotherBankTests(MetaInvoiceLoanTests):
    def test_a_meta_invoice_at_another_bank_is_accepted(self):
        loan = self.approved_loan()
        self.resolve.return_value = "META ADS"
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        response = self.pay(loan, meta_bank_code="100002", meta_account_number="8012345678")  # e.g. Paga
        self.assertEqual(response.status_code, 200, response.content)


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=False)
class MetaInvoiceWithoutAutomaticWithdrawalsTests(MetaInvoiceLoanTests):
    """The Meta invoice flow does not depend on automatic withdrawals being on."""

    def test_the_form_is_offered_and_pay_pays_meta(self):
        self.assertTrue(self.client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])
        loan = self.approved_loan()
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        self.pay(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.DISBURSED)


@override_settings(PAYSTACK_SECRET_KEY="")
class MetaInvoiceWithoutPaystackTests(TestCase):
    def test_without_paystack_the_staff_flow_stays(self):
        user = User.objects.create_user(email="ng@example.com", role=User.Role.AGENT, country="Nigeria")
        Wallet.objects.create(agent=AgentProfile.objects.create(user=user), currency="NGN")
        client = APIClient()
        client.force_authenticate(user)
        self.assertFalse(client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])

