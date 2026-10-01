"""Signing out revokes the session; a used refresh token stops working."""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.cookies import COOKIE_NAME
from apps.applications.tests.factories import make_user


class SessionRevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        make_user("ada@example.com")
        self.client = APIClient()
        response = self.client.post(
            "/api/auth/login/", {"email": "ada@example.com", "password": "Strong-pass-123"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.first = response.cookies[COOKIE_NAME].value

    def refresh_with(self, raw):
        client = APIClient()
        client.cookies[COOKIE_NAME] = raw
        return client.post("/api/auth/refresh/", {}, format="json")

    def test_signing_out_revokes_the_refresh_token(self):
        self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(self.refresh_with(self.first).status_code, 401)

    def test_a_refreshed_token_is_retired_after_the_grace_period(self):
        renewed = self.refresh_with(self.first)
        self.assertEqual(renewed.status_code, 200)
        # A second tab asking at the same moment with the same token still works.
        self.assertEqual(self.refresh_with(self.first).status_code, 200)
        # Once the grace period is over, the old token is dead.
        cache.clear()
        self.assertEqual(self.refresh_with(self.first).status_code, 401)
        # The new one carries on.
        self.assertEqual(self.refresh_with(renewed.cookies[COOKIE_NAME].value).status_code, 200)

    def test_a_signed_out_token_gets_no_grace(self):
        self.refresh_with(self.first)  # rotated: within grace
        client = APIClient()
        client.cookies[COOKIE_NAME] = self.first
        client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(self.refresh_with(self.first).status_code, 401)

    def test_a_token_in_the_request_body_is_not_accepted(self):
        response = APIClient().post("/api/auth/refresh/", {"refresh": self.first}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_a_forged_token_is_refused(self):
        self.assertEqual(self.refresh_with(self.first[:-4] + "abcd").status_code, 401)
