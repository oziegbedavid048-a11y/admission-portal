"""Ads funding never touches an agent's earnings or their withdrawals."""

from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from apps.partners.admin import LoanAdmin
from apps.partners.models import AgentProfile, Commission, Loan, Wallet, Withdrawal


class AdsFundingBalanceTests(TestCase):
    def setUp(self):
        user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        self.wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
        self.wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("150000"))
        self.model_admin = LoanAdmin(Loan, admin.site)

    def run_action(self, name):
        with mock.patch.object(self.model_admin, "message_user"), mock.patch(
            "apps.partners.admin.send_loan_approved_email"
        ):
            getattr(self.model_admin, name)(RequestFactory().post("/admin/"), Loan.objects.all())

    def approve(self, amount):
        Loan.objects.create(agent=self.agent, requested_amount=amount, purpose="Facebook")
        self.run_action("action_approve_and_disburse")

    def wallet_now(self):
        return Wallet.objects.get(pk=self.wallet.pk)

    def test_approving_a_loan_leaves_the_earned_balance_alone(self):
        self.approve(Decimal("80000"))
        wallet = self.wallet_now()
        self.assertEqual(wallet.loan_balance, Decimal("80000"))
        self.assertEqual(wallet.available_balance, Decimal("150000"))

    def test_withdrawals_pay_the_full_amount_with_a_loan_outstanding(self):
        self.approve(Decimal("80000"))
        withdrawal = Withdrawal.request(self.agent, Decimal("100000"))
        self.assertEqual(withdrawal.loan_deduction, Decimal("0"))
        self.assertEqual(withdrawal.net_amount, Decimal("100000"))
        wallet = self.wallet_now()
        self.assertEqual(wallet.loan_balance, Decimal("80000"))
        self.assertEqual(wallet.available_balance, Decimal("50000"))

    def test_the_desk_marks_a_loan_repaid_once(self):
        self.approve(Decimal("80000"))
        self.run_action("action_mark_repaid")
        self.run_action("action_mark_repaid")
        self.assertEqual(Loan.objects.get().status, Loan.Status.REPAID)
        self.assertEqual(self.wallet_now().loan_balance, Decimal("0"))


class RepayAndBorrowTests(TestCase):
    """The Repay button, and one loan at a time."""

    def setUp(self):
        from rest_framework.test import APIClient

        user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        self.wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
        self.wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("150000"))
        self.client = APIClient()
        self.client.force_authenticate(user)

    def disburse(self, amount=Decimal("80000")):
        loan = Loan.objects.create(
            agent=self.agent, requested_amount=amount, approved_amount=amount,
            purpose="Facebook", status=Loan.Status.DISBURSED,
        )
        Wallet.objects.filter(pk=self.wallet.pk).update(loan_balance=amount)
        return loan

    def repay(self, amount):
        return self.client.post("/api/partners/loans/repay/", {"amount": str(amount)}, format="json")

    def request_loan(self):
        return self.client.post(
            "/api/partners/loans/",
            {"requested_amount": "50000", "purpose": "Facebook Ads", "ad_account_link": "https://example.com/ad"},
            format="json",
        )

    def test_partial_repayment_comes_out_of_the_balance(self):
        self.disburse()
        response = self.repay(30000)
        self.assertEqual(response.status_code, 200, response.content)
        wallet = Wallet.objects.get(pk=self.wallet.pk)
        self.assertEqual(wallet.loan_balance, Decimal("50000"))
        self.assertEqual(wallet.loan_repaid_total, Decimal("30000"))
        self.assertEqual(wallet.available_balance, Decimal("120000"))
        self.assertEqual(Loan.objects.get().status, Loan.Status.DISBURSED)

    def test_full_repayment_clears_the_loan_and_allows_a_new_request(self):
        self.disburse()
        self.assertEqual(self.request_loan().status_code, 400)
        self.assertEqual(self.repay(80000).status_code, 200)
        self.assertEqual(Loan.objects.get().status, Loan.Status.REPAID)
        self.assertEqual(self.request_loan().status_code, 201)

    def test_cannot_repay_more_than_owed_or_more_than_available(self):
        self.disburse(Decimal("80000"))
        self.assertEqual(self.repay(90000).status_code, 400)
        Wallet.objects.filter(pk=self.wallet.pk).update(total_withdrawn=Decimal("140000"))
        self.assertEqual(self.repay(20000).status_code, 400)
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).loan_balance, Decimal("80000"))

    def test_cannot_repay_with_nothing_owed(self):
        self.assertEqual(self.repay(1000).status_code, 400)

    def test_only_one_request_in_review_at_a_time(self):
        self.assertEqual(self.request_loan().status_code, 201)
        self.assertEqual(self.request_loan().status_code, 400)
        self.assertEqual(Loan.objects.count(), 1)
