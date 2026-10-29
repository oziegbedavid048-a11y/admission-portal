"""Ads funding paid straight into a Meta ads invoice through Paystack.

The agent gives the invoice (account, bank, amount, expiry) and their Ads
Manager link; Paystack confirms the account is Meta's before the desk sees
it; the desk approves; Paystack pays Meta; only then is the loan owed.
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
        body = {
            "requested_amount": "10000",
            "purpose": "Facebook Ads",
            "ad_account_link": ADS_LINK,
            "meta_bank_code": "999992",
            "meta_account_number": "5624424318",
            "invoice_expires_at": (timezone.now() + timedelta(hours=6)).isoformat(),
            **overrides,
        }
        return self.client.post("/api/partners/loans/", body, format="json")

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

    # ── The request ───────────────────────────────────────────────────

    def test_a_meta_invoice_confirmed_by_paystack_goes_to_the_desk(self):
        response = self.request_loan()
        self.assertEqual(response.status_code, 201, response.content)
        loan = Loan.objects.get()
        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertEqual((loan.meta_account_name, loan.meta_bank_name, loan.meta_account_number), ("Meta Ads", "OPay", "5624424318"))
        self.resolve.assert_called_once_with("5624424318", "999992")
        self.assertEqual(self.owed(), Decimal("0"))  # nothing owed before Meta is paid
        self.assertTrue(self.client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])

    def test_an_account_that_is_not_metas_is_refused(self):
        self.resolve.return_value = "John Doe"
        response = self.request_loan()
        self.assertEqual(response.status_code, 400)
        self.assertIn("not Meta", str(response.json()))
        self.assertFalse(Loan.objects.exists())

    def test_the_link_must_be_facebook_ads_manager(self):
        for link in ("https://example.com/adsmanager?act=123", "https://business.facebook.com/adsmanager", "https://facebook.com.evil.com/?act=1"):
            self.assertEqual(self.request_loan(ad_account_link=link).status_code, 400, link)
        self.assertFalse(Loan.objects.exists())

    def test_an_expired_invoice_is_refused(self):
        expired = (timezone.now() - timedelta(minutes=1)).isoformat()
        self.assertEqual(self.request_loan(invoice_expires_at=expired).status_code, 400)
        self.assertEqual(self.request_loan(invoice_expires_at=None).status_code, 400)
        self.assertFalse(Loan.objects.exists())

    # ── The desk approves; Paystack pays Meta ─────────────────────────

    def test_approval_pays_meta_and_only_then_is_the_loan_owed(self):
        self.request_loan()
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success", "transfer_code": "TRF_1"}).start()
        loan = self.approve(Loan.objects.get())
        self.assertEqual(loan.status, Loan.Status.DISBURSED)
        amount, recipient, reference, _reason = send.call_args[0]
        self.assertEqual((amount, recipient, reference), (Decimal("10000.00"), "RCP_meta", loan.paystack_reference))
        self.assertEqual(self.owed(), Decimal("10000"))
        # Approving again changes nothing and pays nothing.
        self.approve(loan)
        send.assert_called_once()

    def test_a_low_paystack_balance_holds_it_and_sends_it_once_later(self):
        self.request_loan()
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Your balance is not enough")).start()
        loan = self.approve(Loan.objects.get())
        self.assertEqual((loan.status, loan.review_reason), (Loan.Status.APPROVED, LOW_BALANCE_NOTE))
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

    def test_a_failed_payment_to_meta_is_not_owed_and_a_new_request_is_allowed(self):
        self.request_loan()
        mock.patch(f"{P}.send_transfer", return_value={"status": "failed"}).start()
        loan = self.approve(Loan.objects.get())
        self.assertEqual(loan.status, Loan.Status.FAILED)
        self.assertEqual(self.owed(), Decimal("0"))
        self.assertEqual(self.request_loan().status_code, 201)

    def test_a_reversal_after_payment_removes_what_was_owed(self):
        from apps.partners.loan_payouts import apply_status

        self.request_loan()
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        loan = self.approve(Loan.objects.get())
        self.assertEqual(self.owed(), Decimal("10000"))
        apply_status(loan, {"status": "reversed"})
        apply_status(loan, {"status": "reversed"})  # a repeat changes nothing
        loan.refresh_from_db()
        self.assertEqual((loan.status, self.owed()), (Loan.Status.FAILED, Decimal("0")))

    def test_an_invoice_that_expired_before_approval_is_not_paid(self):
        self.request_loan()
        Loan.objects.update(invoice_expires_at=timezone.now() - timedelta(minutes=5))
        send = mock.patch(f"{P}.send_transfer").start()
        loan = self.approve(Loan.objects.get())
        send.assert_not_called()
        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertIn("expired", loan.review_reason)

    def test_the_staff_disburse_action_never_touches_a_meta_invoice_loan(self):
        self.request_loan()
        loan = Loan.objects.get()
        staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        desk = APIClient()
        desk.force_login(staff)
        with mock.patch("apps.partners.admin.send_loan_approved_email"):
            desk.post(reverse("admin:partners_loan_changelist"), {"action": "action_approve_and_disburse", "_selected_action": [loan.pk]})
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertEqual(self.owed(), Decimal("0"))

    # ── Outside Nigeria: as before ─────────────────────────────────────

    def test_an_agent_outside_nigeria_keeps_the_staff_flow(self):
        User.objects.filter(pk=self.user.pk).update(country="Ghana")
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))
        response = self.client.post(
            "/api/partners/loans/", {"requested_amount": "10000", "purpose": "Facebook Ads"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        loan = Loan.objects.get()
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
class MetaAccountRecheckTests(MetaInvoiceLoanTests):
    """The account is checked again with Paystack the moment it is paid."""

    def test_an_account_no_longer_metas_at_payment_is_not_paid(self):
        self.request_loan()
        self.resolve.return_value = "Ade Stores"  # the invoice account changed hands
        send = mock.patch(f"{P}.send_transfer").start()
        loan = self.approve(Loan.objects.get())
        send.assert_not_called()
        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertIn("not Meta", loan.review_reason)
        self.assertEqual(self.owed(), Decimal("0"))

    def test_a_meta_invoice_at_another_bank_is_accepted(self):
        self.resolve.return_value = "META ADS"
        response = self.request_loan(meta_bank_code="100002", meta_account_number="8012345678")  # e.g. Paga
        self.assertEqual(response.status_code, 201, response.content)


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=False)
class MetaInvoiceWithoutAutomaticWithdrawalsTests(MetaInvoiceLoanTests):
    """The Meta invoice form does not depend on automatic withdrawals being on."""

    def test_the_form_is_offered_and_approval_pays_meta(self):
        self.assertTrue(self.client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])
        self.assertEqual(self.request_loan().status_code, 201)
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        loan = self.approve(Loan.objects.get())
        self.assertEqual(loan.status, Loan.Status.DISBURSED)


@override_settings(PAYSTACK_SECRET_KEY="")
class MetaInvoiceWithoutPaystackTests(TestCase):
    def test_without_paystack_the_staff_flow_stays(self):
        user = User.objects.create_user(email="ng@example.com", role=User.Role.AGENT, country="Nigeria")
        Wallet.objects.create(agent=AgentProfile.objects.create(user=user), currency="NGN")
        client = APIClient()
        client.force_authenticate(user)
        self.assertFalse(client.get("/api/partners/wallet/").json()["ads_paid_to_meta"])

