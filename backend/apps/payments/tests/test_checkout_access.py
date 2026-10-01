"""Checkout only ever acts on a file the caller is allowed to see."""

from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.tests.factories import make_application, make_user
from apps.payments.models import Payment


class CheckoutAccessTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", full_name="Ada Owner")
        self.application = make_application(self.owner, phone="+2348000000000")
        self.client = APIClient()

    def checkout(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            "/api/payments/checkout/", {"application": self.application.reference}, format="json"
        )

    def test_another_applicant_gets_not_found_and_no_data(self):
        stranger = make_user("stranger@example.com")
        response = self.checkout(stranger)
        self.assertEqual(response.status_code, 404)
        body = response.content.decode()
        self.assertNotIn("owner@example.com", body)
        self.assertNotIn("+2348000000000", body)
        # The victim's file is untouched: no payment opened, no notification.
        self.assertFalse(Payment.objects.filter(application=self.application).exists())
        self.assertFalse(self.application.notifications.exists())

    def test_an_unrelated_agent_gets_not_found(self):
        from apps.partners.models import AgentProfile

        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        AgentProfile.objects.create(user=agent_user)
        response = self.checkout(agent_user)
        self.assertEqual(response.status_code, 404)

    def test_unknown_reference_is_not_found(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post("/api/payments/checkout/", {"application": "APP-000000"}, format="json")
        self.assertEqual(response.status_code, 404)

    @mock.patch("apps.payments.views.gateway.initiate", return_value="https://checkout.paystack.test/x")
    def test_the_owner_can_still_check_out(self, _initiate):
        response = self.checkout(self.owner)
        self.assertIn(response.status_code, (200, 201), response.content)
        self.assertEqual(response.json()["application"]["reference"], self.application.reference)
