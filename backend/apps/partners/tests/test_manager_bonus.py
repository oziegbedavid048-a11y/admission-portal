"""A sales manager's bonus is earned when the student's fee is paid, once."""

from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.applications.constants import SUPERVISOR_BONUS_NGN
from apps.applications.tests.factories import make_application, make_user
from apps.partners.models import AgentProfile, SupervisorBonus, SupervisorProfile
from apps.payments.models import Payment
from apps.payments.settlement import settle


class ManagerBonusTests(TestCase):
    def setUp(self):
        manager_user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        self.manager = SupervisorProfile.objects.create(user=manager_user)
        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=agent_user, supervisor=self.manager)
        student = make_user("student@example.com")
        self.application = make_application(student, submitted_by_agent=self.agent)

    def pay(self, status=Payment.Status.PENDING):
        return Payment.objects.create(
            application=self.application,
            amount=Decimal("200000"),
            processing_fee=Decimal("0"),
            amount_ngn=Decimal("200000"),
            processing_fee_ngn=Decimal("0"),
            status=status,
        )

    def bonus_total(self):
        return SupervisorProfile.objects.get(pk=self.manager.pk).bonus_total

    def test_no_bonus_before_the_fee_is_paid(self):
        from apps.applications import services

        self.pay()
        self.assertEqual(services.award_supervisor_bonus(self.application), 0)
        self.assertEqual(self.bonus_total(), Decimal("0"))
        self.assertFalse(SupervisorBonus.objects.exists())

    def test_paying_the_fee_earns_the_bonus_once(self):
        payment = self.pay()
        self.assertTrue(settle(payment, gateway_name="Paystack"))
        self.assertFalse(settle(payment, gateway_name="Paystack"))
        self.assertEqual(self.bonus_total(), SUPERVISOR_BONUS_NGN)
        self.assertEqual(SupervisorBonus.objects.count(), 1)

    def test_a_waived_fee_earns_no_bonus(self):
        from apps.applications import services

        self.pay(status=Payment.Status.WAIVED)
        self.assertEqual(services.award_supervisor_bonus(self.application), 0)
        self.assertEqual(self.bonus_total(), Decimal("0"))
