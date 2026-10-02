"""The desk's superuser is kept in step with the environment without being
signed out on every start-up."""

import os
from unittest import mock

from django.apps import apps
from django.test import TestCase

from apps.accounts.apps import auto_ensure_admin
from apps.accounts.models import User

ENV = {"DJANGO_ADMIN_EMAIL": "Desk@Example.com", "DJANGO_ADMIN_PASSWORD": "Desk-pass-123"}


class AutoAdminTests(TestCase):
    def run_hook(self):
        auto_ensure_admin(sender=apps.get_app_config("accounts"))

    @mock.patch.dict(os.environ, ENV)
    def test_creates_the_superuser(self):
        self.run_hook()
        user = User.objects.get(email="desk@example.com")
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertTrue(user.check_password("Desk-pass-123"))

    @mock.patch.dict(os.environ, ENV)
    def test_restarting_does_not_rewrite_the_password(self):
        self.run_hook()
        first = User.objects.get(email="desk@example.com").password
        self.run_hook()
        self.assertEqual(User.objects.get(email="desk@example.com").password, first)

    def test_a_new_password_in_the_environment_still_resets_it(self):
        with mock.patch.dict(os.environ, ENV):
            self.run_hook()
        with mock.patch.dict(os.environ, {**ENV, "DJANGO_ADMIN_PASSWORD": "New-pass-456"}):
            self.run_hook()
        self.assertTrue(User.objects.get(email="desk@example.com").check_password("New-pass-456"))


class AdminSignInTests(TestCase):
    """The admin sign-in page finds the desk however the email is typed."""

    def setUp(self):
        with mock.patch.dict(os.environ, ENV):
            auto_ensure_admin(sender=apps.get_app_config("accounts"))

    def sign_in(self, email, password="Desk-pass-123"):
        return self.client.post("/admin/login/", {"username": email, "password": password, "next": "/admin/"})

    def test_signs_in_with_the_exact_address(self):
        self.assertEqual(self.sign_in("desk@example.com").status_code, 302)

    def test_signs_in_with_capital_letters_or_stray_spaces(self):
        self.assertEqual(self.sign_in("Desk@Example.com").status_code, 302)
        self.client.logout()
        self.assertEqual(self.sign_in("  DESK@EXAMPLE.COM ").status_code, 302)

    def test_a_wrong_password_still_fails(self):
        response = self.sign_in("Desk@Example.com", "wrong-password-1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "correct email address and password")

    def test_a_non_staff_account_cannot_use_the_admin(self):
        User.objects.create_user(email="ada@example.com", password="Ada-pass-1234")
        response = self.sign_in("ADA@example.com", "Ada-pass-1234")
        self.assertEqual(response.status_code, 200)

    def test_the_hook_updates_an_existing_mixed_case_account_instead_of_adding_one(self):
        User.objects.all().delete()
        old = User.objects.create(email="Desk@Example.com", is_staff=False)
        old.set_password("Old-pass-123")
        old.save()
        with mock.patch.dict(os.environ, ENV):
            auto_ensure_admin(sender=apps.get_app_config("accounts"))
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertEqual(user.email, "desk@example.com")
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password("Desk-pass-123"))
        self.assertEqual(self.sign_in("desk@example.com").status_code, 302)

    def test_two_accounts_differing_only_in_case_are_never_guessed_between(self):
        User.objects.all().delete()
        first = User.objects.create(email="twin1@example.com")
        second = User.objects.create(email="twin2@example.com")
        # save() lower-cases addresses, so differing-case twins can only exist
        # from older data; build them past it.
        User.objects.filter(pk=first.pk).update(email="Twin@Example.com")
        User.objects.filter(pk=second.pk).update(email="TWIN@example.com")
        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("twin@example.com")


class PastedPasswordTests(TestCase):
    """A space or quote marks pasted around the password on the host are not
    part of the password the person types."""

    def run_hook(self, password):
        with mock.patch.dict(os.environ, {"DJANGO_ADMIN_EMAIL": "Desk@Example.com", "DJANGO_ADMIN_PASSWORD": password}):
            auto_ensure_admin(sender=apps.get_app_config("accounts"))

    def sign_in(self, password):
        return self.client.post("/admin/login/", {"username": "desk@example.com", "password": password, "next": "/admin/"})

    def test_trailing_space_and_newline_are_dropped(self):
        self.run_hook("Desk-pass-123 \n")
        self.assertEqual(self.sign_in("Desk-pass-123").status_code, 302)

    def test_surrounding_quotes_are_dropped(self):
        self.run_hook('"Desk-pass-123"')
        self.assertEqual(self.sign_in("Desk-pass-123").status_code, 302)

    def test_quotes_inside_the_password_are_kept(self):
        self.run_hook("Desk\"pass-123")
        self.assertEqual(self.sign_in("Desk\"pass-123").status_code, 302)

    def test_the_password_is_not_written_to_the_log(self):
        with self.assertLogs("apps.accounts.apps", level="WARNING") as captured:
            self.run_hook(" Desk-pass-123 ")
        text = "\n".join(captured.output)
        self.assertNotIn("Desk-pass-123", text)
        self.assertIn("desk@example.com", text)


class AdminRefusalLogTests(TestCase):
    """A refused admin sign-in says why in the log, without any secret."""

    def setUp(self):
        with mock.patch.dict(os.environ, ENV):
            auto_ensure_admin(sender=apps.get_app_config("accounts"))
        User.objects.create_user(email="ada@example.com", password="Ada-pass-1234")

    def refused(self, username, password):
        with self.assertLogs("config.admin_login", level="WARNING") as captured:
            self.client.post("/admin/login/", {"username": username, "password": password, "next": "/admin/"})
        return "\n".join(captured.output)

    def test_unknown_address(self):
        self.assertIn("no account has the address nobody@example.com", self.refused("Nobody@Example.com", "x" * 12))

    def test_wrong_password(self):
        text = self.refused("desk@example.com", "wrong-password-9")
        self.assertIn("the password does not match the account desk@example.com", text)

    def test_not_a_staff_account(self):
        text = self.refused("ada@example.com", "Ada-pass-1234")
        self.assertIn("ada@example.com is not a staff account", text)

    def test_a_password_in_the_first_box_is_never_logged(self):
        text = self.refused("MySecretPassw0rd", "whatever-pass-1")
        self.assertIn("did not hold an email address", text)
        self.assertNotIn("MySecretPassw0rd", text)

    def test_the_typed_password_is_never_logged(self):
        text = self.refused("desk@example.com", "wrong-password-9")
        self.assertNotIn("wrong-password-9", text)
