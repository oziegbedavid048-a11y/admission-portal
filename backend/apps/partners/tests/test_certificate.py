"""The partnership certificate appears in the portal six hours after sign-up."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.partners.models import AgentProfile


class AgentCertificateTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="agent@example.com", full_name="Ada Agent", role=User.Role.AGENT, country="Nigeria"
        )
        self.agent = AgentProfile.objects.create(user=user, agency_name="Ada Travels")
        self.client = APIClient()
        self.client.force_authenticate(user)

    def age(self, hours):
        AgentProfile.objects.filter(pk=self.agent.pk).update(
            created_at=timezone.now() - timedelta(hours=hours)
        )
        # A fresh user, as a real request loads, not one holding the old profile.
        self.client.force_authenticate(User.objects.get(pk=self.agent.user_id))

    def test_hidden_before_six_hours(self):
        self.age(5.9)
        self.assertFalse(self.client.get("/api/partners/me/").json()["certificate_ready"])
        self.assertEqual(self.client.get("/api/partners/certificate/").status_code, 404)

    def test_ready_after_six_hours(self):
        self.age(6.1)
        self.assertTrue(self.client.get("/api/partners/me/").json()["certificate_ready"])
        response = self.client.get("/api/partners/certificate/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_only_agents_can_fetch_it(self):
        applicant = User.objects.create_user(email="student@example.com", role=User.Role.APPLICANT)
        client = APIClient()
        client.force_authenticate(applicant)
        self.assertEqual(client.get("/api/partners/certificate/").status_code, 403)
