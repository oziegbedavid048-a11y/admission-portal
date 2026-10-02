"""A paid fee is a record of money: the admin cannot delete or hand-edit it,
and a file whose fee was already confirmed is never charged again."""

from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.tests.factories import make_application, make_user
from apps.partners.models import AgentProfile, Commission, Loan, Wallet, Withdrawal
from apps.partners.models import SupervisorProfile, SupervisorWithdrawal
from apps.payments.models import Payment


def payment_for(application, status):
    return Payment.objects.create(
        application=application,
        amount=Decimal("200000"),
        amount_ngn=Decimal("200000"),
        currency="NGN",
        status=status,
    )


class PaymentAdminTests(TestCase):
    def setUp(self):
        self.desk = User.objects.create_superuser(email="desk@example.com", password="Desk-pass-123")
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.desk
        self.model_admin = admin.site._registry[Payment]
        self.application = make_application(make_user("ada@example.com"))

    def test_a_paid_waived_or_reviewed_fee_cannot_be_deleted(self):
        for status in (Payment.Status.PAID, Payment.Status.WAIVED, Payment.Status.REVIEW):
            Payment.objects.filter(application=self.application).delete()
            payment = payment_for(self.application, status)
            self.assertFalse(self.model_admin.has_delete_permission(self.request, payment), status)

    def test_an_abandoned_attempt_can_be_removed(self):
        for status in (Payment.Status.PENDING, Payment.Status.FAILED):
            Payment.objects.filter(application=self.application).delete()
            payment = payment_for(self.application, status)
            self.assertTrue(self.model_admin.has_delete_permission(self.request, payment), status)

    def test_status_and_amounts_are_read_only_and_none_can_be_added(self):
        readonly = self.model_admin.get_readonly_fields(self.request)
        for field in ("status", "application", "amount", "amount_ngn", "gateway", "paid_at"):
            self.assertIn(field, readonly)
        self.assertFalse(self.model_admin.has_add_permission(self.request))

    def test_bulk_delete_in_the_admin_refuses_a_paid_fee(self):
        payment = payment_for(self.application, Payment.Status.PAID)
        self.client.force_login(self.desk)
        self.client.post(
            "/admin/payments/payment/",
            {"action": "delete_selected", "_selected_action": [payment.pk], "post": "yes"},
        )
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())

    def test_deleting_the_application_does_not_take_a_paid_fee_with_it(self):
        payment_for(self.application, Payment.Status.PAID)
        self.client.force_login(self.desk)
        self.client.post(
            f"/admin/applications/application/{self.application.pk}/delete/", {"post": "yes"}
        )
        self.assertTrue(Payment.objects.filter(application=self.application).exists())


class PayoutAdminTests(TestCase):
    def setUp(self):
        self.desk = User.objects.create_superuser(email="desk@example.com", password="Desk-pass-123")
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.desk
        agent = AgentProfile.objects.create(user=make_user("agent@example.com", role=User.Role.AGENT))
        Wallet.objects.get_or_create(agent=agent)
        self.agent = agent

    def test_payouts_cannot_be_added_or_deleted_by_hand(self):
        for model in (Withdrawal, SupervisorWithdrawal):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(self.request), model)
            self.assertFalse(model_admin.has_delete_permission(self.request), model)

    def test_paid_out_funding_cannot_be_deleted_but_a_declined_request_can(self):
        model_admin = admin.site._registry[Loan]
        paid_out = Loan.objects.create(agent=self.agent, requested_amount=Decimal("20000"), purpose="Facebook", status=Loan.Status.DISBURSED)
        declined = Loan.objects.create(agent=self.agent, requested_amount=Decimal("20000"), purpose="Facebook", status=Loan.Status.DECLINED)
        self.assertFalse(model_admin.has_delete_permission(self.request, paid_out))
        self.assertTrue(model_admin.has_delete_permission(self.request, declined))
        self.assertIn("status", model_admin.get_readonly_fields(self.request, paid_out))

    def test_wallet_totals_are_read_only(self):
        from apps.partners.admin import WalletInline

        inline = WalletInline(AgentProfile, admin.site)
        readonly = inline.get_readonly_fields(self.request)
        for field in ("total_earned", "total_withdrawn", "loan_balance", "registration_commission_total"):
            self.assertIn(field, readonly)


class NoSecondChargeTests(TestCase):
    """A file whose fee was confirmed but whose payment record is missing."""

    def setUp(self):
        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=agent_user)
        Wallet.objects.get_or_create(agent=self.agent)
        self.application = make_application(make_user("s@example.com"), submitted_by_agent=self.agent)
        self.client = APIClient()
        self.client.force_authenticate(agent_user)

    @mock.patch("apps.payments.views.gateway.initiate", return_value="https://checkout.paystack.test/x")
    def test_checkout_refuses_when_the_commission_was_already_paid(self, _initiate):
        Commission.objects.create(
            agent=self.agent, application=self.application, kind=Commission.Kind.REGISTRATION, amount=Decimal("30000")
        )
        response = self.client.post(
            "/api/payments/checkout/", {"application": self.application.reference, "return_to": "agent"}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already confirmed", response.json()["detail"])
        _initiate.assert_not_called()

    @mock.patch("apps.payments.views.gateway.initiate", return_value="https://checkout.paystack.test/x")
    def test_checkout_refuses_when_the_fee_check_is_ticked(self, _initiate):
        type(self.application).objects.filter(pk=self.application.pk).update(payment_verified=True)
        response = self.client.post(
            "/api/payments/checkout/", {"application": self.application.reference, "return_to": "agent"}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        _initiate.assert_not_called()

    @mock.patch("apps.payments.views.gateway.initiate", return_value="https://checkout.paystack.test/x")
    def test_an_ordinary_unpaid_file_can_still_be_paid(self, _initiate):
        response = self.client.post(
            "/api/payments/checkout/", {"application": self.application.reference, "return_to": "agent"}, format="json"
        )
        self.assertIn(response.status_code, (200, 201), response.content[:300])
