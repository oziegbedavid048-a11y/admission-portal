"""Automatic agent payouts through Paystack, against simulated Paystack replies."""

import hashlib
import hmac
import json
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
from apps.partners.models import AgentProfile, Commission, Wallet, Withdrawal
from apps.partners.payouts import check

KEY = "sk_test_simulated"
P = "apps.partners.paystack_transfers"


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=True)
class PayoutTests(TestCase):
    def setUp(self):
        cache.clear()  # the withdrawal rate limit lives in the cache
        self.user = User.objects.create_user(
            email="agent@example.com", full_name="Ada Agent", role=User.Role.AGENT, country="Nigeria"
        )
        self.agent = AgentProfile.objects.create(
            user=self.user, bank_name="Guaranty Trust Bank", account_number="0123456789",
            account_name="ADA AGENT", bank_code="058", account_verified_at=timezone.now(),
        )
        self.wallet = Wallet.objects.create(agent=self.agent, currency="NGN")
        self.wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("900000"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.recipient = mock.patch(f"{P}.create_recipient", return_value="RCP_test").start()
        self.addCleanup(mock.patch.stopall)

    def fresh_client(self):
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))

    def withdraw(self, amount="150000"):
        response = self.client.post("/api/partners/withdrawals/", {"amount": amount}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return Withdrawal.objects.get(pk=response.json()["withdrawal"]["id"])

    def available(self):
        return Wallet.objects.get(pk=self.wallet.pk).available_balance

    # ── Who is paid automatically ─────────────────────────────────────

    def test_no_payout_waits_for_staff_not_the_first_and_not_a_large_one(self):
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        first = self.withdraw()
        large = self.withdraw("600000")
        self.assertEqual((first.status, large.status), (Withdrawal.Status.PAID, Withdrawal.Status.PAID))
        self.assertEqual((first.review_reason, large.review_reason), ("", ""))
        self.assertEqual(send.call_count, 2)

    def test_a_payout_is_sent_at_once_and_marked_paid_when_paystack_confirms(self):
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success", "transfer_code": "TRF_1"}).start()
        sent_email = mock.patch("apps.accounts.emails.send_agent_payout_sent_email").start()
        with self.captureOnCommitCallbacks(execute=True):
            withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)
        self.assertEqual(withdrawal.transfer_code, "TRF_1")
        amount, recipient, reference, _reason = send.call_args[0]
        # The agent receives exactly what they asked for; the company pays the fee.
        self.assertEqual((amount, recipient), (Decimal("150000.00"), "RCP_test"))
        self.assertEqual(reference, withdrawal.paystack_reference)
        sent_email.assert_called_once()

    @override_settings(PAYSTACK_PAYOUTS_ENABLED=False)
    def test_switched_off_means_paid_by_staff(self):
        send = mock.patch(f"{P}.send_transfer").start()
        withdrawal = self.withdraw()
        self.assertEqual((withdrawal.method, withdrawal.status), (Withdrawal.Method.MANUAL, Withdrawal.Status.PENDING))
        send.assert_not_called()

    def test_agents_outside_nigeria_are_paid_by_staff(self):
        self.user.country = "Ghana"
        self.user.save()
        self.fresh_client()
        send = mock.patch(f"{P}.send_transfer").start()
        self.assertEqual(self.withdraw().method, Withdrawal.Method.MANUAL)
        send.assert_not_called()

    def test_withdrawals_pause_after_the_payout_account_changes(self):
        AgentProfile.objects.filter(pk=self.agent.pk).update(payout_account_changed_at=timezone.now())
        self.fresh_client()
        send = mock.patch(f"{P}.send_transfer").start()
        response = self.client.post("/api/partners/withdrawals/", {"amount": "150000"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("paused", str(response.json()))
        self.assertFalse(Withdrawal.objects.filter(agent=self.agent).exists())
        send.assert_not_called()

    def test_the_pause_ends_after_a_day(self):
        AgentProfile.objects.filter(pk=self.agent.pk).update(
            payout_account_changed_at=timezone.now() - timedelta(hours=25)
        )
        self.fresh_client()
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        self.assertEqual(self.withdraw().status, Withdrawal.Status.PAID)

    def test_an_unverified_account_is_paid_by_staff(self):
        AgentProfile.objects.filter(pk=self.agent.pk).update(account_verified_at=None)
        self.fresh_client()
        self.assertEqual(self.withdraw().method, Withdrawal.Method.MANUAL)

    # ── What Paystack reports ─────────────────────────────────────────

    def test_sending_then_webhook_success(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.SENDING)
        self.post_webhook("transfer.success", withdrawal)
        self.post_webhook("transfer.success", withdrawal)  # a repeat changes nothing
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)

    def test_webhook_failure_refunds_once(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        before = self.available()
        withdrawal = self.withdraw()
        self.assertEqual(self.available(), before - Decimal("150000"))
        self.post_webhook("transfer.failed", withdrawal)
        self.post_webhook("transfer.failed", withdrawal)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(self.available(), before)

    def test_a_reversal_after_success_refunds(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        before = self.available()
        withdrawal = self.withdraw()
        self.post_webhook("transfer.reversed", withdrawal)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(self.available(), before)

    def test_a_webhook_with_the_wrong_amount_is_ignored(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        withdrawal = self.withdraw()
        self.post_webhook("transfer.success", withdrawal, amount=100)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.SENDING)

    def test_paystack_refusing_holds_the_money_for_staff(self):
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Your balance is not enough")).start()
        before = self.available()
        withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)
        self.assertIn("balance is not enough", withdrawal.failure_reason)
        # Not refunded on its own: staff send it again or refund it.
        self.assertEqual(self.available(), before - Decimal("150000"))

    def test_no_clear_answer_stays_sending_until_checked(self):
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackUnreachable("timed out")).start()
        withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.SENDING)
        mock.patch(f"{P}.verify_transfer", return_value={"status": "success"}).start()
        self.assertEqual(check(withdrawal).status, Withdrawal.Status.PAID)

    def test_an_otp_request_goes_back_to_staff_with_instructions(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "otp"}).start()
        withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)
        self.assertIn("OTP", withdrawal.failure_reason)

    # ── Staff ─────────────────────────────────────────────────────────

    def test_staff_send_again_after_paystack_refused(self):
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Your balance is not enough")).start()
        withdrawal = self.withdraw()  # refused: held for staff
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        self.client.force_login(staff)
        response = self.client.post(
            reverse("admin:partners_withdrawal_changelist"),
            {"action": "action_approve_and_send", "_selected_action": [withdrawal.pk]},
        )
        self.assertEqual(response.status_code, 302)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)
        self.assertEqual(withdrawal.approved_by, staff)
        send.assert_called_once()

    def test_staff_cannot_refund_a_payout_that_is_sending(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        withdrawal = self.withdraw()
        staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        self.client.force_login(staff)
        self.client.post(
            reverse("admin:partners_withdrawal_changelist"),
            {"action": "action_mark_failed", "_selected_action": [withdrawal.pk]},
        )
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.SENDING)

    # ── Helpers ───────────────────────────────────────────────────────

    def post_webhook(self, event, withdrawal, amount=None):
        body = json.dumps({
            "event": event,
            "data": {
                "reference": withdrawal.paystack_reference,
                "amount": amount if amount is not None else paystack.kobo(withdrawal.net_amount),
                "status": event.split(".")[1],
            },
        }).encode()
        signature = hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()
        response = APIClient().post(
            "/api/payments/webhook/paystack/", body, content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)


@override_settings(PAYSTACK_SECRET_KEY=KEY)
class PayoutAccountVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="agent@example.com", password="Strong-pass-123", role=User.Role.AGENT, country="Nigeria"
        )
        self.agent = AgentProfile.objects.create(
            user=self.user, bank_name="gtb", account_number="1111111111", account_name="typed name"
        )
        Wallet.objects.create(agent=self.agent)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        mock.patch(f"{P}.list_banks", return_value=[{"name": "Guaranty Trust Bank", "code": "058"}]).start()
        self.addCleanup(mock.patch.stopall)

    def update(self, **data):
        return self.client.patch(
            "/api/partners/me/", {"current_password": "Strong-pass-123", **data}, format="json"
        )

    def test_a_bank_picked_from_the_list_is_verified_and_named_by_paystack(self):
        mock.patch(f"{P}.resolve_account", return_value="ADA AGENT").start()
        response = self.update(bank_code="058", account_number="0123456789")
        self.assertEqual(response.status_code, 200, response.content)
        self.agent.refresh_from_db()
        self.assertEqual((self.agent.bank_name, self.agent.account_name), ("Guaranty Trust Bank", "ADA AGENT"))
        self.assertIsNotNone(self.agent.account_verified_at)
        self.assertTrue(response.json()["account_verified"])

    def test_a_different_account_starts_the_pause_but_confirming_the_same_one_does_not(self):
        mock.patch(f"{P}.resolve_account", return_value="ADA AGENT").start()
        AgentProfile.objects.filter(pk=self.agent.pk).update(bank_name="Guaranty Trust Bank")
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))
        self.update(bank_code="058", account_number="1111111111")  # same account, now confirmed
        self.agent.refresh_from_db()
        self.assertIsNone(self.agent.payout_account_changed_at)
        self.update(bank_code="058", account_number="0123456789")  # a different account
        self.agent.refresh_from_db()
        self.assertIsNotNone(self.agent.payout_account_changed_at)

    def test_an_account_paystack_cannot_find_is_refused(self):
        mock.patch(f"{P}.resolve_account", side_effect=paystack.PaystackRejected("not found")).start()
        response = self.update(bank_code="058", account_number="0000000000")
        self.assertEqual(response.status_code, 400)
        self.agent.refresh_from_db()
        self.assertIsNone(self.agent.account_verified_at)

    def test_changing_the_account_again_clears_the_old_recipient(self):
        mock.patch(f"{P}.resolve_account", return_value="ADA AGENT").start()
        AgentProfile.objects.filter(pk=self.agent.pk).update(paystack_recipient_code="RCP_old")
        self.update(bank_code="058", account_number="0123456789")
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.paystack_recipient_code, "")

    def test_bank_list_and_name_check(self):
        mock.patch(f"{P}.resolve_account", return_value="ADA AGENT").start()
        self.assertEqual(self.client.get("/api/partners/banks/").json()["banks"][0]["code"], "058")
        response = self.client.post(
            "/api/partners/banks/resolve/", {"bank_code": "058", "account_number": "0123456789"}, format="json"
        )
        self.assertEqual(response.json(), {"account_name": "ADA AGENT"})


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=True)
class SalesManagerPayoutTests(TestCase):
    def setUp(self):
        from apps.partners.models import SupervisorProfile

        cache.clear()
        self.user = User.objects.create_user(
            email="manager@example.com", password="Strong-pass-123", full_name="Sam Manager",
            role=User.Role.SUPERVISOR,
        )
        self.manager = SupervisorProfile.objects.create(
            user=self.user, bank_name="Access Bank", account_number="0123456789", account_name="SAM MANAGER",
            bank_code="044", account_verified_at=timezone.now(), bonus_total=Decimal("400000"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        mock.patch(f"{P}.create_recipient", return_value="RCP_mgr").start()
        self.addCleanup(mock.patch.stopall)

    def withdraw(self, amount="120000"):
        from apps.partners.models import SupervisorWithdrawal

        response = self.client.post("/api/supervisors/withdrawals/", {"amount": amount}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return SupervisorWithdrawal.objects.get(pk=response.json()["withdrawal"]["id"])

    def available(self):
        from apps.partners.models import SupervisorProfile

        return SupervisorProfile.objects.get(pk=self.manager.pk).available_balance

    def test_even_the_first_payout_goes_at_once(self):
        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        first = self.withdraw()
        self.assertEqual((first.method, first.status), (Withdrawal.Method.PAYSTACK, Withdrawal.Status.PAID))
        self.assertTrue(first.paystack_reference.startswith("gabstep-sm-"))
        self.assertEqual(send.call_args[0][0], Decimal("120000.00"))

    def test_a_failed_transfer_returns_the_money(self):
        from apps.partners.models import SupervisorWithdrawal

        SupervisorWithdrawal.objects.create(supervisor=self.manager, amount=Decimal("10000"), status=Withdrawal.Status.PAID)
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        before = self.available()
        withdrawal = self.withdraw()
        self.assertEqual(withdrawal.status, Withdrawal.Status.SENDING)
        body = json.dumps({"event": "transfer.failed", "data": {
            "reference": withdrawal.paystack_reference, "amount": paystack.kobo(withdrawal.amount), "status": "failed",
        }}).encode()
        signature = hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()
        APIClient().post("/api/payments/webhook/paystack/", body, content_type="application/json",
                         HTTP_X_PAYSTACK_SIGNATURE=signature)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(self.available(), before)

    def test_an_unverified_manager_is_paid_by_staff(self):
        from apps.partners.models import SupervisorProfile

        SupervisorProfile.objects.filter(pk=self.manager.pk).update(account_verified_at=None)
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))
        self.assertEqual(self.withdraw().method, Withdrawal.Method.MANUAL)

    def test_the_manager_s_bank_is_verified_by_paystack(self):
        from apps.partners.models import SupervisorProfile

        mock.patch(f"{P}.list_banks", return_value=[{"name": "Zenith Bank", "code": "057"}]).start()
        mock.patch(f"{P}.resolve_account", return_value="SAM MANAGER").start()
        self.assertEqual(self.client.get("/api/supervisors/banks/").json()["banks"][0]["code"], "057")
        response = self.client.patch("/api/supervisors/me/", {
            "bank_code": "057", "account_number": "2222222222", "current_password": "Strong-pass-123",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        manager = SupervisorProfile.objects.get(pk=self.manager.pk)
        self.assertEqual((manager.bank_name, manager.account_name), ("Zenith Bank", "SAM MANAGER"))
        self.assertIsNotNone(manager.account_verified_at)
