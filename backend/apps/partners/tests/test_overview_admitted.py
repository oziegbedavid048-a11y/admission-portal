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

    def test_the_agent_students_table_reads_a_lettered_student_as_admitted(self):
        self.letter(self.students[0], Letter.Kind.ADMISSION)
        response = self.client.get("/api/partners/students/")
        self.assertEqual(response.status_code, 200)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        by_ref = {row["reference"]: row["status"] for row in rows}
        self.assertEqual(by_ref[self.students[0].reference], "admission_granted")
        self.assertNotEqual(by_ref[self.students[1].reference], "admission_granted")


class SalesManagerAdmittedTests(TestCase):
    """The sales manager sees the same Admitted figures as the agent."""

    def setUp(self):
        from apps.partners.models import SupervisorProfile

        manager_user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        self.manager = SupervisorProfile.objects.create(user=manager_user)
        agent_user = make_user("agent2@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=agent_user, supervisor=self.manager)
        Wallet.objects.get_or_create(agent=self.agent)
        self.client = APIClient()
        self.client.force_authenticate(manager_user)
        self.students = [
            make_application(make_user(f"m{i}@example.com"), submitted_by_agent=self.agent)
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

    def test_overview_counts_letters_and_the_agent_table_matches(self):
        Application.objects.filter(pk=self.students[0].pk).update(status=Application.Status.ADMITTED)
        self.letter(self.students[1], Letter.Kind.ADMISSION)
        self.letter(self.students[2], Letter.Kind.ADMISSION, published=False)

        overview = self.client.get("/api/supervisors/overview/")
        self.assertEqual(overview.status_code, 200, overview.content[:300])
        self.assertEqual(overview.data["stats"]["admitted"], 2)
        self.assertEqual(overview.data["pipeline"]["admitted"], 2)

        agents = self.client.get("/api/supervisors/agents/")
        self.assertEqual(agents.status_code, 200)
        rows = agents.data["results"] if isinstance(agents.data, dict) else agents.data
        self.assertEqual(rows[0]["admitted"], 2)

    def test_the_students_table_reads_a_lettered_student_as_admitted(self):
        self.letter(self.students[1], Letter.Kind.OFFER)
        response = self.client.get("/api/supervisors/students/")
        self.assertEqual(response.status_code, 200)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        by_ref = {row["reference"]: row["status"] for row in rows}
        self.assertEqual(by_ref[self.students[1].reference], "admission_granted")
        self.assertNotEqual(by_ref[self.students[0].reference], "admission_granted")

    def test_a_rejected_file_stays_rejected_even_with_a_letter(self):
        Application.objects.filter(pk=self.students[0].pk).update(status=Application.Status.REJECTED)
        self.letter(self.students[0], Letter.Kind.ADMISSION)
        response = self.client.get("/api/supervisors/students/")
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        by_ref = {row["reference"]: row["status"] for row in rows}
        self.assertEqual(by_ref[self.students[0].reference], "rejected")
