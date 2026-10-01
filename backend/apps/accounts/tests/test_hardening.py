"""Smaller hardening: verification links, sign-in format, error text, the
exchange-rate endpoint, API docs and correction tickets."""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.verification import make_token
from apps.applications.models import CorrectionRequest
from apps.applications.tests.factories import make_application, make_user


class VerificationLinkTests(TestCase):
    def test_a_link_signs_in_only_the_first_time(self):
        user = make_user("ada@example.com", email_verified=False)
        token = make_token(user)
        client = APIClient()
        first = client.post("/api/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertIn("access", first.json())
        second = APIClient().post("/api/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertNotIn("access", second.json())
        self.assertTrue(second.json()["already"])


class LoginFormatTests(TestCase):
    def test_sign_in_refuses_a_plain_html_form(self):
        make_user("ada@example.com")
        response = APIClient().post(
            "/api/auth/login/", {"email": "ada@example.com", "password": "Strong-pass-123"}, format="multipart"
        )
        self.assertEqual(response.status_code, 415)
        ok = APIClient().post(
            "/api/auth/login/", {"email": "ada@example.com", "password": "Strong-pass-123"}, format="json"
        )
        self.assertEqual(ok.status_code, 200)


class ErrorTextTests(TestCase):
    def test_checkout_failure_does_not_reveal_internals(self):
        user = make_user("ada@example.com")
        application = make_application(user)
        client = APIClient()
        client.force_authenticate(user)
        with mock.patch("apps.payments.views.quote_for", side_effect=RuntimeError("secret db detail")):
            response = client.post("/api/payments/checkout/", {"application": application.reference}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("secret db detail", response.content.decode())


class ExchangeRateTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_malformed_currency_is_refused_without_an_outbound_call(self):
        with mock.patch("apps.catalog.fx._from_provider") as provider:
            response = APIClient().get("/api/catalog/exchange-rates/", {"base": "US D"})
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()

    def test_the_public_cannot_bypass_the_cache(self):
        with mock.patch("apps.catalog.fx._from_provider", return_value={"base": "NGN", "rates": {}, "live": True}) as provider:
            client = APIClient()
            client.get("/api/catalog/exchange-rates/", {"base": "NGN"})
            for _ in range(3):
                client.get("/api/catalog/exchange-rates/", {"base": "NGN", "refresh": "true"})
        self.assertEqual(provider.call_count, 1)


class ApiDocsTests(TestCase):
    def test_schema_and_docs_are_not_public(self):
        self.assertIn(APIClient().get("/api/schema/").status_code, (401, 403))
        self.assertIn(APIClient().get("/api/docs/").status_code, (401, 403))


class CorrectionTicketTests(TestCase):
    def test_tickets_come_from_a_large_space(self):
        application = make_application(make_user("ada@example.com"))
        tickets = {
            CorrectionRequest.objects.create(application=application, field="Name", corrected_value="x").ticket
            for _ in range(20)
        }
        self.assertEqual(len(tickets), 20)
        for ticket in tickets:
            self.assertRegex(ticket, r"^TK-[A-Z2-9]{8}$")
