"""No payout can be paid twice, refunded after it left, or taken from money
the agent does not have — whatever Paystack, staff or the agent do.
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
from apps.partners.models import AgentProfile, Commission, Wallet, Withdrawal
from apps.partners.payouts import LOW_BALANCE_NOTE, resend_low_balance

KEY = "sk_test_simulated"
P = "apps.partners.paystack_transfers"
LOW = paystack.PaystackRejected("Your balance is not enough to fulfil this request")
NOT_FOUND = paystack.PaystackRejected("Transfer not found")


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_PAYOUTS_ENABLED=True)
class PayoutMoneySafetyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="agent@example.com", full_name="Ada Agent", role=User.Role.AGENT, country="Nigeria"
        )
        self.agent = AgentProfile.objects.create(
            user=self.user, bank_name="Guaranty Trust Bank", account_number="0123456789",
            account_name="ADA AGENT", bank_code="058", account_verified_at=timezone.now(),
        )
        self.wallet = Wallet.objects.create(agent=self.agent, currency="NGN")
        self.wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("300000"))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        mock.patch(f"{P}.create_recipient", return_value="RCP_test").start()
        self.verify = mock.patch(f"{P}.verify_transfer", side_effect=NOT_FOUND).start()
        self.addCleanup(mock.patch.stopall)

    def request_payout(self, amount="150000"):
        return self.client.post("/api/partners/withdrawals/", {"amount": amount}, format="json")

    def available(self):
        return Wallet.objects.get(pk=self.wallet.pk).available_balance

    def staff_action(self, action, withdrawal):
        staff = User.objects.create_superuser(email=f"desk-{action}@example.com", password="pw-123456")
        client = APIClient()
        client.force_login(staff)
        return client.post(
            reverse("admin:partners_withdrawal_changelist"),
            {"action": action, "_selected_action": [withdrawal.pk]},
        )

    # ── The balance moves the moment a payout is asked for ─────────────

    def test_the_amount_leaves_the_balance_instantly_and_cannot_be_asked_for_twice(self):
        mock.patch(f"{P}.send_transfer", return_value={"status": "pending"}).start()
        self.assertEqual(self.request_payout("200000").status_code, 201)
        self.assertEqual(self.available(), Decimal("100000"))
        # The same money again is refused; only what is left can be asked for.
        second = self.request_payout("200000")
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Withdrawal.objects.count(), 1)

    # ── Paystack's own balance is too low ─────────────────────────────

    def test_a_low_paystack_balance_holds_the_payout_and_tells_the_agent_plainly(self):
        mock.patch(f"{P}.send_transfer", side_effect=LOW).start()
        response = self.request_payout()
        self.assertEqual(response.status_code, 201)
        body = response.content.decode()
        # The agent sees an ordinary "requested" payout, never Paystack's words
        # about the company's balance.
        self.assertNotIn("not enough", body)
        self.assertEqual(response.json()["withdrawal"]["status"], Withdrawal.Status.PENDING)
        withdrawal = Withdrawal.objects.get()
        self.assertEqual(withdrawal.review_reason, LOW_BALANCE_NOTE)
        # Held, not refunded: it is still on its way to the agent.
        self.assertEqual(self.available(), Decimal("150000"))

    def test_after_a_top_up_the_held_payout_is_sent_once_under_the_same_reference(self):
        mock.patch(f"{P}.send_transfer", side_effect=LOW).start()
        self.request_payout()
        withdrawal = Withdrawal.objects.get()
        reference = withdrawal.paystack_reference
        Withdrawal.objects.filter(pk=withdrawal.pk).update(sent_at=timezone.now() - timedelta(hours=1))

        send = mock.patch(f"{P}.send_transfer", return_value={"status": "success"}).start()
        resend_low_balance()
        resend_low_balance()  # the cron runs again: nothing more is sent
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)
        send.assert_called_once()
        self.assertEqual(send.call_args[0][2], reference)
        self.assertEqual(self.available(), Decimal("150000"))

    def test_while_the_balance_is_still_low_the_payout_stays_held(self):
        mock.patch(f"{P}.send_transfer", side_effect=LOW).start()
        self.request_payout()
        Withdrawal.objects.update(sent_at=timezone.now() - timedelta(hours=1))
        resend_low_balance()
        withdrawal = Withdrawal.objects.get()
        self.assertEqual((withdrawal.status, withdrawal.review_reason), (Withdrawal.Status.PENDING, LOW_BALANCE_NOTE))
        self.assertEqual(self.available(), Decimal("150000"))

    # ── A refusal that hides a transfer that did go out ───────────────

    def test_a_duplicate_reference_refusal_is_not_put_back_for_staff(self):
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Duplicate Transfer Reference")).start()
        self.verify.side_effect = None
        self.verify.return_value = {"status": "success"}
        self.request_payout()
        withdrawal = Withdrawal.objects.get()
        # Paystack already paid it: it is recorded as paid, not left for review.
        self.assertEqual(withdrawal.status, Withdrawal.Status.PAID)

    def test_no_answer_while_checking_a_refusal_leaves_it_sending(self):
        mock.patch(f"{P}.send_transfer", side_effect=paystack.PaystackRejected("Something odd")).start()
        self.verify.side_effect = paystack.PaystackUnreachable("timed out")
        self.request_payout()
        # Unknown whether it went: never back in review, so never refundable by hand.
        self.assertEqual(Withdrawal.objects.get().status, Withdrawal.Status.SENDING)

    # ── Staff cannot pay twice or refund money that left ──────────────

    def held_payout(self):
        mock.patch(f"{P}.send_transfer", side_effect=LOW).start()
        self.request_payout()
        return Withdrawal.objects.get()

    def test_staff_cannot_refund_a_held_payout_paystack_actually_has(self):
        withdrawal = self.held_payout()
        self.verify.side_effect = None
        self.verify.return_value = {"status": "pending"}
        self.staff_action("action_mark_failed", withdrawal)
        withdrawal.refresh_from_db()
        self.assertNotEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(self.available(), Decimal("150000"))

    def test_staff_cannot_mark_paid_by_hand_a_payout_paystack_has(self):
        withdrawal = self.held_payout()
        self.verify.side_effect = None
        self.verify.return_value = {"status": "success"}
        self.staff_action("action_mark_paid", withdrawal)
        withdrawal.refresh_from_db()
        # Paystack paid it, so it is paid through Paystack, not by staff too.
        self.assertEqual((withdrawal.status, withdrawal.method), (Withdrawal.Status.PAID, Withdrawal.Method.PAYSTACK))

    def test_staff_can_refund_a_held_payout_paystack_never_received(self):
        withdrawal = self.held_payout()
        self.staff_action("action_mark_failed", withdrawal)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(self.available(), Decimal("300000"))

    def test_staff_cannot_refund_when_paystack_cannot_be_asked(self):
        withdrawal = self.held_payout()
        self.verify.side_effect = paystack.PaystackUnreachable("timed out")
        self.staff_action("action_mark_failed", withdrawal)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)
        self.assertEqual(self.available(), Decimal("150000"))

    def test_a_refund_from_a_stale_list_skips_a_payout_sent_meanwhile(self):
        withdrawal = self.held_payout()
        stale = Withdrawal.objects.get(pk=withdrawal.pk)
        Withdrawal.objects.filter(pk=withdrawal.pk).update(status=Withdrawal.Status.SENDING)
        self.assertFalse(stale.refund_if_pending("Marked as failed by staff."))
        self.assertEqual(Withdrawal.objects.get(pk=withdrawal.pk).status, Withdrawal.Status.SENDING)
        self.assertEqual(self.available(), Decimal("150000"))
