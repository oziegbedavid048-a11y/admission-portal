"""Money written to a wallet is never lost to a stale copy, and never refunded twice."""

from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from apps.partners.admin import WithdrawalAdmin
from apps.partners.models import (
    AgentProfile,
    Commission,
    SupervisorProfile,
    SupervisorWithdrawal,
    Wallet,
    Withdrawal,
)


def make_agent(email="agent@example.com"):
    user = make_user(email, role=User.Role.AGENT)
    agent = AgentProfile.objects.create(user=user)
    wallet, _ = Wallet.objects.get_or_create(agent=agent)
    return agent, wallet


class WalletLostUpdateTests(TestCase):
    def test_a_commission_on_a_stale_copy_keeps_the_withdrawal(self):
        agent, wallet = make_agent()
        wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("100000"))

        # A copy read before the withdrawal, as a settlement running at the
        # same moment would hold.
        stale = Wallet.objects.get(pk=wallet.pk)
        amount = Withdrawal.MIN_AMOUNT
        Withdrawal.request(agent, amount)

        stale.credit_commission(Commission.Kind.VISA, Decimal("50000"))

        fresh = Wallet.objects.get(pk=wallet.pk)
        self.assertEqual(fresh.total_withdrawn, amount)
        self.assertEqual(fresh.total_earned, Decimal("150000"))
        self.assertEqual(fresh.visa_commission_total, Decimal("50000"))
        self.assertEqual(fresh.available_balance, Decimal("150000") - amount)

    def test_a_bonus_on_a_stale_copy_keeps_the_payout(self):
        user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        manager = SupervisorProfile.objects.create(user=user)
        manager.credit_bonus(SupervisorWithdrawal.MIN_AMOUNT)
        stale = SupervisorProfile.objects.get(pk=manager.pk)
        SupervisorWithdrawal.request(manager, SupervisorWithdrawal.MIN_AMOUNT)

        stale.credit_bonus(Decimal("2000"))

        fresh = SupervisorProfile.objects.get(pk=manager.pk)
        self.assertEqual(fresh.total_withdrawn, SupervisorWithdrawal.MIN_AMOUNT)
        self.assertEqual(fresh.bonus_total, SupervisorWithdrawal.MIN_AMOUNT + Decimal("2000"))


class RefundOnceTests(TestCase):
    def test_manager_payout_already_paid_is_not_refunded(self):
        user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        manager = SupervisorProfile.objects.create(user=user)
        manager.credit_bonus(SupervisorWithdrawal.MIN_AMOUNT)
        payout = SupervisorWithdrawal.request(manager, SupervisorWithdrawal.MIN_AMOUNT)
        SupervisorWithdrawal.objects.filter(pk=payout.pk).update(status=SupervisorWithdrawal.Status.PAID)

        # The stale copy still says pending.
        self.assertFalse(payout.mark_failed())
        self.assertEqual(SupervisorProfile.objects.get(pk=manager.pk).total_withdrawn, SupervisorWithdrawal.MIN_AMOUNT)

    def test_manager_payout_fails_and_refunds_exactly_once(self):
        user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        manager = SupervisorProfile.objects.create(user=user)
        manager.credit_bonus(SupervisorWithdrawal.MIN_AMOUNT)
        payout = SupervisorWithdrawal.request(manager, SupervisorWithdrawal.MIN_AMOUNT)
        twin = SupervisorWithdrawal.objects.get(pk=payout.pk)

        self.assertTrue(payout.mark_failed())
        self.assertFalse(twin.mark_failed())
        self.assertEqual(SupervisorProfile.objects.get(pk=manager.pk).total_withdrawn, Decimal("0"))

    @mock.patch("apps.partners.admin.send_agent_payout_failed_email")
    def test_agent_payout_failed_twice_refunds_once(self, _email):
        agent, wallet = make_agent()
        wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("100000"))
        Withdrawal.request(agent, Withdrawal.MIN_AMOUNT)

        model_admin = WithdrawalAdmin(Withdrawal, admin.site)
        request = RequestFactory().post("/admin/")
        with mock.patch.object(model_admin, "message_user"):
            model_admin.action_mark_failed(request, Withdrawal.objects.all())
            model_admin.action_mark_failed(request, Withdrawal.objects.all())

        self.assertEqual(Wallet.objects.get(pk=wallet.pk).total_withdrawn, Decimal("0"))

    def test_status_cannot_be_edited_by_hand(self):
        self.assertIn("status", WithdrawalAdmin.readonly_fields)
        from apps.partners.supervisor_admin import SupervisorWithdrawalAdmin

        self.assertIn("status", SupervisorWithdrawalAdmin.readonly_fields)
