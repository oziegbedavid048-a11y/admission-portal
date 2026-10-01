"""A new sales manager is emailed their sign-in details and the sign-in link."""

from django.core import mail
from django.test import TestCase

from apps.accounts.models import User
from apps.partners.models import SupervisorProfile


class ManagerWelcomeTests(TestCase):
    def setUp(self):
        desk = User.objects.create_superuser(email="desk@example.com", password="Desk-pass-123", full_name="Desk")
        self.client.force_login(desk)

    def create_manager(self):
        return self.client.post(
            "/admin/partners/supervisorprofile/add/",
            {
                "email": "Kemi.Manager@example.com",
                "full_name": "Kemi Manager",
                "phone": "",
                "password": "Manager-pass-789",
                "region": "Lagos",
                "bank_name": "",
                "account_number": "",
                "account_name": "",
                "is_active": "on",
                "agents-TOTAL_FORMS": "0",
                "agents-INITIAL_FORMS": "0",
                "bonuses-TOTAL_FORMS": "0",
                "bonuses-INITIAL_FORMS": "0",
            },
        )

    def test_creating_a_manager_emails_their_sign_in_details(self):
        mail.outbox.clear()
        response = self.create_manager()
        self.assertIn(response.status_code, (200, 302), response.content[:500])
        profile = SupervisorProfile.objects.get(user__email="kemi.manager@example.com")
        self.assertTrue(profile.user.check_password("Manager-pass-789"))

        sent = [m for m in mail.outbox if "kemi.manager@example.com" in m.to]
        self.assertEqual(len(sent), 1)
        body = sent[0].body
        self.assertIn("Manager-pass-789", body)
        self.assertIn("/sales-manager/login", body)
        self.assertIn(profile.agent_code, body)

    def test_editing_a_manager_does_not_email_again(self):
        self.create_manager()
        profile = SupervisorProfile.objects.get(user__email="kemi.manager@example.com")
        mail.outbox.clear()
        self.client.post(
            f"/admin/partners/supervisorprofile/{profile.pk}/change/",
            {
                "email": "kemi.manager@example.com",
                "full_name": "Kemi Renamed",
                "phone": "",
                "password": "",
                "region": "Lagos",
                "bank_name": "",
                "account_number": "",
                "account_name": "",
                "is_active": "on",
                "agents-TOTAL_FORMS": "0",
                "agents-INITIAL_FORMS": "0",
                "bonuses-TOTAL_FORMS": "0",
                "bonuses-INITIAL_FORMS": "0",
            },
        )
        self.assertEqual(len(mail.outbox), 0)
