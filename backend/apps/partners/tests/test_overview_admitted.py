"""The agent overview counts a student as admitted once the desk marks the file
admitted or publishes an admission or offer letter for it."""

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application, Letter
from apps.applications.tests.factories import make_application, make_user
from apps.partners.models import AgentProfile, Wallet


class OverviewAdmittedTests(TestCase):
    def setUp(self):
        user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=user)
        Wallet.objects.get_or_create(agent=self.agent)
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.students = [
            make_application(make_user(f"s{i}@example.com"), submitted_by_agent=self.agent)
            for i in range(3)
        ]

    def letter(self, application, kind, published=True):
        return Letter.objects.create(
            application=application,
            kind=kind,
            title="Letter",
            file=ContentFile(b"%PDF-1.4", name="letter.pdf"),
            is_published=published,
        )

    def stats(self):
        response = self.client.get("/api/partners/overview/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_nobody_is_admitted_at_first(self):
        data = self.stats()
        self.assertEqual(data["stats"]["admitted"], 0)
        self.assertNotIn("visas_verified", data["stats"])

    def test_a_published_admission_letter_counts(self):
        self.letter(self.students[0], Letter.Kind.ADMISSION)
        data = self.stats()
        self.assertEqual(data["stats"]["admitted"], 1)
        self.assertEqual(data["pipeline"]["admitted"], 1)

    def test_an_offer_letter_counts_too(self):
        self.letter(self.students[1], Letter.Kind.OFFER)
        self.assertEqual(self.stats()["stats"]["admitted"], 1)

    def test_an_unpublished_or_other_letter_does_not(self):
        self.letter(self.students[0], Letter.Kind.ADMISSION, published=False)
        self.letter(self.students[1], Letter.Kind.VISA)
        self.assertEqual(self.stats()["stats"]["admitted"], 0)

    def test_marked_admitted_and_lettered_count_once(self):
        Application.objects.filter(pk=self.students[0].pk).update(status=Application.Status.ADMITTED)
        self.letter(self.students[0], Letter.Kind.ADMISSION)
        self.letter(self.students[2], Letter.Kind.OFFER)
        self.assertEqual(self.stats()["stats"]["admitted"], 2)
