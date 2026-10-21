"""Fixes from the October 2026 security and reliability audit.

* changing the password while signed in is rate limited,
* saving a profile writes only what was edited, never an old copy of the row,
* oversized API requests are refused before they are read,
* an unexpected error answers as JSON, not as Django's HTML error page.
"""

from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.applications.tests.factories import make_user


class PasswordChangeLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("ada@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @mock.patch.object(
        SimpleRateThrottle, "THROTTLE_RATES", {"user": "1000/min", "password_change": "3/hour"}
    )
    def test_guessing_the_current_password_is_stopped(self):
        for _ in range(3):
            response = self.client.post(
                "/api/auth/password/",
                {"current_password": "wrong-guess", "new_password": "Another-pass-456"},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/auth/password/",
            {"current_password": "Strong-pass-123", "new_password": "Another-pass-456"},
            format="json",
        )
        self.assertEqual(response.status_code, 429)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Strong-pass-123"))


class StaleUserSaveTests(TestCase):
    def test_editing_the_profile_does_not_undo_a_password_change_made_meanwhile(self):
        user = make_user("ada@example.com")
        stale = User.objects.get(pk=user.pk)  # what the request loaded

        # Meanwhile, a password reset and a deactivation land.
        fresh = User.objects.get(pk=user.pk)
        fresh.set_password("Changed-pass-789")
        fresh.is_active = False
        fresh.save()

        request = RequestFactory().patch("/api/auth/me/")
        request.user = stale
        serializer = UserSerializer(stale, data={"phone": "+2348011112222"}, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        user.refresh_from_db()
        self.assertEqual(user.phone, "+2348011112222")
        self.assertTrue(user.check_password("Changed-pass-789"))
        self.assertFalse(user.is_active)


class BodySizeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_a_huge_json_body_is_refused_unread(self):
        body = '{"email": "a@example.com", "password": "' + "x" * (3 * 1024 * 1024) + '"}'
        response = self.client.generic("POST", "/api/auth/login/", body, content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["code"], "request_too_large")

    def test_a_normal_request_is_untouched(self):
        response = self.client.post(
            "/api/auth/login/", {"email": "nobody@example.com", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_the_admin_keeps_its_own_limit(self):
        # Only /api/ is capped here; the admin's long custom messages still fit.
        body = "x" * (3 * 1024 * 1024)
        response = self.client.generic("POST", "/admin/login/", body, content_type="text/plain")
        self.assertNotEqual(response.status_code, 413)


class ServerErrorShapeTests(TestCase):
    def test_an_unexpected_error_answers_as_json(self):
        user = make_user("ada@example.com")
        client = APIClient()
        client.force_authenticate(user)
        with mock.patch(
            "apps.accounts.views.WhatsAppContact.objects.filter", side_effect=RuntimeError("db password=secret")
        ), self.assertLogs("gabstep.api", level="ERROR"):
            response = client.get("/api/auth/support/whatsapp/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "server_error")
        self.assertNotIn("secret", response.content.decode())
