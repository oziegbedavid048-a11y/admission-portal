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
