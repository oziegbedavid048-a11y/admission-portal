"""Approving Ads funding from the admin works on PostgreSQL.

The admin's loan list loads each agent's wallet with an outer join. Locking
that query (SELECT ... FOR UPDATE) is refused by PostgreSQL, so every
"Approve and disburse" failed on the live site. SQLite ignores locking, which
is why the other tests never saw it. These go through the real admin screen
and check that the lock is taken on the loans alone.
"""

from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from apps.partners.admin import LoanAdmin, locked_loans
from apps.partners.models import AgentProfile, Loan, Wallet


class LoanAdminLockTests(TestCase):
    def setUp(self):
        user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        Wallet.objects.create(agent=self.agent)
        self.loan = Loan.objects.create(agent=self.agent, requested_amount=Decimal("50000"), purpose="Facebook")
        self.staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")

    def admin_queryset(self):
        request = RequestFactory().get("/admin/")
        request.user = self.staff
        return LoanAdmin(Loan, admin.site).get_queryset(request)

    def test_the_admin_list_query_has_the_outer_join_that_postgres_cannot_lock(self):
        self.assertIn("LEFT OUTER JOIN", str(self.admin_queryset().query))

    def test_the_lock_is_taken_on_the_loans_alone(self):
        locked = locked_loans(self.admin_queryset())
        self.assertTrue(locked.query.select_for_update)
        self.assertNotIn("JOIN", str(locked.query))
        self.assertEqual(list(locked), [self.loan])

    def run_action(self, action):
        self.client.force_login(self.staff)
        with mock.patch("apps.partners.admin.send_loan_approved_email"):
            return self.client.post(
                reverse("admin:partners_loan_changelist"),
                {"action": action, "_selected_action": [self.loan.pk]},
            )

    def test_approve_and_disburse_from_the_admin_screen(self):
        response = self.run_action("action_approve_and_disburse")
        self.assertEqual(response.status_code, 302)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.Status.DISBURSED)
        self.assertEqual(Wallet.objects.get(agent=self.agent).loan_balance, Decimal("50000"))

    def test_mark_repaid_from_the_admin_screen(self):
        self.run_action("action_approve_and_disburse")
        self.run_action("action_mark_repaid")
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.Status.REPAID)
        self.assertEqual(Wallet.objects.get(agent=self.agent).loan_balance, Decimal("0"))
