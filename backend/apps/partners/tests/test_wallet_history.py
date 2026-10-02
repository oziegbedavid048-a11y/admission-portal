"""The agent's earning history: every commission in, every repayment and
withdrawal out, each with its own date and time."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.tests.factories import make_application, make_user
from apps.partners.models import AgentProfile, Commission, LoanRepayment, Wallet, Withdrawal


class WalletHistoryTests(TestCase):
    def setUp(self):
        user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        self.wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
        self.client = APIClient()
        self.client.force_authenticate(user)

        student = make_user("student@example.com", full_name="Ada Obi")
        self.application = make_application(student, submitted_by_agent=self.agent)
        Commission.objects.create(
            agent=self.agent,
            application=self.application,
            kind=Commission.Kind.REGISTRATION,
            amount=Decimal("150000"),
        )
        self.wallet.credit_commission(Commission.Kind.REGISTRATION, Decimal("150000"))

    def history(self):
        response = self.client.get("/api/partners/wallet/history/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_a_commission_is_money_in(self):
        rows = self.history()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["direction"], "in")
        self.assertEqual(rows[0]["title"], "Registration commission")
        self.assertEqual(rows[0]["detail"], "Ada Obi")
        self.assertEqual(rows[0]["amount"], "150000.00")
        self.assertTrue(rows[0]["at"])

    def test_each_repayment_is_recorded_and_listed_as_money_out(self):
        Wallet.objects.filter(pk=self.wallet.pk).update(loan_balance=Decimal("50000"))
        wallet = Wallet.objects.get(pk=self.wallet.pk)
        wallet.repay_loan(Decimal("20000"))
        wallet = Wallet.objects.get(pk=self.wallet.pk)
        wallet.repay_loan(Decimal("30000"))

        self.assertEqual(
            sorted(LoanRepayment.objects.filter(agent=self.agent).values_list("amount", flat=True)),
            [Decimal("20000.00"), Decimal("30000.00")],
        )
        out = [row for row in self.history() if row["direction"] == "out"]
        self.assertEqual(sorted(row["amount"] for row in out), ["20000.00", "30000.00"])
        self.assertTrue(all(row["title"] == "Ads funding repaid" for row in out))

    def test_withdrawals_are_money_out_but_a_failed_one_is_not(self):
        paid = Withdrawal.request(self.agent, Decimal("100000"))
        Withdrawal.objects.filter(pk=paid.pk).update(status=Withdrawal.Status.PAID)
        failed = Withdrawal.objects.create(
            agent=self.agent,
            amount_requested=Decimal("100000"),
            net_amount=Decimal("100000"),
            status=Withdrawal.Status.FAILED,
        )
        references = [row["reference"] for row in self.history() if row["title"] == "Withdrawal"]
        self.assertEqual(references, [paid.reference])
        self.assertNotIn(failed.reference, references)

    def test_newest_first(self):
        from datetime import timedelta

        from django.utils import timezone

        Commission.objects.filter(agent=self.agent).update(earned_at=timezone.now() - timedelta(hours=1))
        Wallet.objects.filter(pk=self.wallet.pk).update(loan_balance=Decimal("10000"))
        Wallet.objects.get(pk=self.wallet.pk).repay_loan(Decimal("10000"))
        rows = self.history()
        self.assertEqual([row["title"] for row in rows], ["Ads funding repaid", "Registration commission"])

    def test_only_the_agents_own_money_is_listed(self):
        other_user = make_user("other@example.com", role=User.Role.AGENT)
        other = AgentProfile.objects.create(user=other_user)
        LoanRepayment.objects.create(agent=other, amount=Decimal("999"))
        self.assertNotIn("999.00", [row["amount"] for row in self.history()])

    def test_an_applicant_cannot_read_it(self):
        applicant = make_user("someone@example.com")
        client = APIClient()
        client.force_authenticate(applicant)
        self.assertEqual(client.get("/api/partners/wallet/history/").status_code, 403)
