"""The admin sign-in page stops password guessing."""

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import User
from config import admin_login


class AdminLoginLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_superuser(email="desk@example.com", password="Desk-pass-123", full_name="Desk Admin")

    def attempt(self, password, username="desk@example.com", address="203.0.113.5"):
        return self.client.post(
            "/admin/login/",
            {"username": username, "password": password},
            HTTP_CF_CONNECTING_IP=address,
        )

    def test_the_right_password_signs_in(self):
        response = self.attempt("Desk-pass-123")
        self.assertEqual(response.status_code, 302)

    def test_an_address_is_stopped_after_too_many_wrong_passwords(self):
        for _ in range(admin_login.MAX_PER_ADDRESS):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        # Even the right password is refused until the window passes.
        self.assertEqual(self.attempt("Desk-pass-123").status_code, 429)
        # Someone else, elsewhere, is not affected.
        self.client.logout()
        self.assertEqual(
            self.attempt("Desk-pass-123", address="198.51.100.9").status_code, 302
        )

    def test_an_account_is_protected_across_many_addresses(self):
        for i in range(admin_login.MAX_PER_ACCOUNT):
            self.attempt("wrong", address=f"198.18.0.{i + 1}")
        self.assertEqual(self.attempt("wrong", address="198.18.1.1").status_code, 429)

    def test_a_successful_sign_in_clears_the_count(self):
        for _ in range(admin_login.MAX_PER_ADDRESS - 1):
            self.attempt("wrong")
        self.assertEqual(self.attempt("Desk-pass-123").status_code, 302)
        self.client.logout()
        self.assertEqual(self.attempt("wrong").status_code, 200)
