"""Changing where payouts go needs the password, is announced, and does not
move payouts already requested."""

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from apps.partners.models import (
    AgentProfile,
    Commission,
    SupervisorProfile,
    Wallet,
    Withdrawal,
)

PASSWORD = "Strong-pass-123"
OLD = {"bank_name": "Old Bank", "account_number": "0123456789", "account_name": "Kemi Agent"}
NEW = {"bank_name": "Thief Bank", "account_number": "9876543210", "account_name": "Someone Else"}


class AgentPayoutAccountTests(TestCase):
    def setUp(self):
        self.user = make_user("agent@example.com", role=User.Role.AGENT, full_name="Kemi Agent")
        self.agent = AgentProfile.objects.create(user=self.user, **OLD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def patch(self, payload):
        return self.client.patch("/api/partners/me/", payload, format="json")

    def test_bank_change_without_password_is_refused(self):
        response = self.patch(NEW)
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json())
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.account_number, OLD["account_number"])

    def test_bank_change_with_wrong_password_is_refused(self):
        response = self.patch({**NEW, "current_password": "not-it"})
        self.assertEqual(response.status_code, 400)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.bank_name, OLD["bank_name"])

    @mock.patch("apps.accounts.emails.send_payout_account_changed_email")
    def test_bank_change_with_password_saves_and_tells_the_owner(self, announce):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.patch({**NEW, "current_password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn("current_password", response.json())
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.account_number, NEW["account_number"])
        announce.assert_called_once()

    def test_other_profile_fields_do_not_need_the_password(self):
        response = self.patch({"full_name": "Kemi Renamed", **OLD})
        self.assertEqual(response.status_code, 200, response.content)

    def test_a_payout_keeps_the_account_it_was_requested_for(self):
        wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
        wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("100000"))
        withdrawal = Withdrawal.request(self.agent, Withdrawal.MIN_AMOUNT)
        self.patch({**NEW, "current_password": PASSWORD})

        withdrawal.refresh_from_db()
        self.assertIn(OLD["account_number"], withdrawal.paid_to)
        from django.contrib import admin

        from apps.partners.admin import WithdrawalAdmin

        shown = WithdrawalAdmin(Withdrawal, admin.site).destination(withdrawal)
        self.assertIn(OLD["account_number"], shown)
        self.assertNotIn(NEW["account_number"], shown)


class ManagerPayoutAccountTests(TestCase):
    def test_sales_manager_bank_change_needs_the_password(self):
        user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        SupervisorProfile.objects.create(user=user, **OLD)
        client = APIClient()
        client.force_authenticate(user)
        refused = client.patch("/api/supervisors/me/", NEW, format="json")
        self.assertEqual(refused.status_code, 400)
        allowed = client.patch("/api/supervisors/me/", {**NEW, "current_password": PASSWORD}, format="json")
        self.assertEqual(allowed.status_code, 200, allowed.content)
