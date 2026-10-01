"""An agent can only file under a new email or one of their own students."""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application
from apps.applications.tests.factories import make_user
from apps.catalog.models import DestinationCountry, OriginCountry
from apps.partners.models import AgentProfile


def make_agent(email):
    user = make_user(email, role=User.Role.AGENT)
    return user, AgentProfile.objects.create(user=user)


class AgentStudentEmailTests(TestCase):
    def setUp(self):
        OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="N", ngn_per_unit=Decimal("1"))
        DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        self.agent_user, self.agent = make_agent("agent@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.agent_user)

    def file(self, email, client=None):
        return (client or self.client).post(
            "/api/partners/students/",
            {
                "full_name": "Tobi Student",
                "email": email,
                "phone": "+2348000000000",
                "origin_country": "Nigeria",
                "destination_country": "Canada",
                "previous_schools": "School",
                "qualification": "BSc",
                "year_graduated": 2020,
                "grade_gpa": "4.0",
                "is_custom_course": True,
                "custom_course_name": "Nursing",
            },
            format="json",
        )

    def test_a_new_email_creates_the_student(self):
        response = self.file("new.student@example.com")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(User.objects.filter(email="new.student@example.com").exists())

    def test_an_existing_applicants_email_is_refused(self):
        victim = make_user("real.applicant@example.com", full_name="Real Applicant")
        response = self.file("Real.Applicant@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())
        self.assertFalse(Application.objects.filter(applicant=victim).exists())

    def test_staff_and_agent_emails_are_refused(self):
        make_user("desk@example.com", role=User.Role.STAFF, is_staff=True)
        make_agent("other.agent@example.com")
        self.assertEqual(self.file("desk@example.com").status_code, 400)
        self.assertEqual(self.file("other.agent@example.com").status_code, 400)

    def test_the_same_agent_can_file_again_for_their_own_student(self):
        self.assertEqual(self.file("tobi@example.com").status_code, 201)
        self.assertEqual(self.file("tobi@example.com").status_code, 201)
        self.assertEqual(Application.objects.filter(applicant__email="tobi@example.com").count(), 2)

    def test_another_agent_cannot_file_for_that_student(self):
        self.assertEqual(self.file("tobi@example.com").status_code, 201)
        other_user, _ = make_agent("rival@example.com")
        rival = APIClient()
        rival.force_authenticate(other_user)
        self.assertEqual(self.file("tobi@example.com", client=rival).status_code, 400)
