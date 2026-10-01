"""Rate limits hold, and cannot be dodged by varying X-Forwarded-For."""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.models import User
from apps.applications.tests.factories import make_user
from config.throttles import edge_ip, forwarded_client_ip

RATES = {
    "anon": "1000/min",
    "user": "1000/min",
    "login": "3/min",
    "money": "2/hour",
    "payment_status": "3/min",
    "edge": "5/min",
}


class _Request:
    def __init__(self, **meta):
        self.META = meta


class IdentityTests(TestCase):
    def test_first_forwarded_address_is_the_client(self):
        request = _Request(HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.1", REMOTE_ADDR="10.0.0.2")
        self.assertEqual(forwarded_client_ip(request), "203.0.113.7")

    def test_garbage_forwarded_value_falls_back_to_socket(self):
        request = _Request(HTTP_X_FORWARDED_FOR="not-an-ip", REMOTE_ADDR="10.0.0.2")
        self.assertEqual(forwarded_client_ip(request), "10.0.0.2")

    def test_edge_ip_prefers_the_platform_header(self):
        request = _Request(HTTP_CF_CONNECTING_IP="198.51.100.4", REMOTE_ADDR="10.0.0.2")
        self.assertEqual(edge_ip(request), "198.51.100.4")
        self.assertEqual(edge_ip(_Request(REMOTE_ADDR="10.0.0.2")), "10.0.0.2")


@mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", RATES)
class ThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def login(self, forwarded, email="nobody@example.com"):
        # A different email per attempt keeps the per-account lockout out of
        # the way, so only the rate limits are being measured.
        return self.client.post(
            "/api/auth/login/",
            {"email": email, "password": "wrong-password"},
            format="json",
            HTTP_X_FORWARDED_FOR=forwarded,
        )

    def test_login_limit_holds_for_one_client(self):
        codes = [self.login("203.0.113.7", f"user{i}@example.com").status_code for i in range(4)]
        self.assertNotEqual(codes[2], 429)
        self.assertEqual(codes[3], 429)

    def test_varying_forwarded_for_does_not_escape_the_edge_limit(self):
        # Each request claims a new client address, as an attacker going
        # straight to Render would. The connection address stays the same.
        codes = [self.login(f"198.18.0.{i}", f"user{i}@example.com").status_code for i in range(1, 8)]
        self.assertIn(429, codes)
        self.assertLessEqual(codes.index(429), 5)

    def test_two_real_clients_do_not_share_a_login_allowance(self):
        for _ in range(3):
            self.login("203.0.113.7")
        self.assertNotEqual(self.login("203.0.113.8").status_code, 429)

    def test_money_limit_applies_to_requests_that_move_money(self):
        from apps.partners.models import AgentProfile, Wallet

        user = make_user("agent@example.com", role=User.Role.AGENT)
        agent = AgentProfile.objects.create(user=user)
        Wallet.objects.get_or_create(agent=agent)
        self.client.force_authenticate(user)
        codes = [
            self.client.post("/api/partners/withdrawals/", {"amount": "1"}, format="json").status_code
            for _ in range(3)
        ]
        self.assertEqual(codes[2], 429)
        # Reading is not limited by it.
        self.assertEqual(self.client.get("/api/partners/withdrawals/").status_code, 200)

    def test_payment_status_is_limited_for_anonymous_callers(self):
        codes = [
            self.client.get("/api/payments/status/APP-123456/", HTTP_X_FORWARDED_FOR="203.0.113.9").status_code
            for _ in range(4)
        ]
        self.assertEqual(codes[3], 429)
