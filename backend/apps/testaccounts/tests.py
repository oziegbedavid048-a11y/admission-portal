"""Test accounts stay off the working admin screens and receive no email."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.emails import send_async_email
from apps.accounts.models import User
from apps.applications.models import Application
from apps.catalog.models import DestinationCountry, OriginCountry
from apps.partners.models import AgentProfile


class TestAccountSeparationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        origin = OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="₦", ngn_per_unit=1)
        destination = DestinationCountry.objects.create(name="Spain", code="ES", currency="EUR")

        def agent(email, is_test):
            user = User.objects.create_user(
                email=email, full_name=email.split("@")[0], role=User.Role.AGENT, is_test_account=is_test
            )
            return AgentProfile.objects.create(user=user, agency_name=f"{email} agency")

        def student(email, agent_profile, is_test):
            user = User.objects.create_user(email=email, full_name=email.split("@")[0], is_test_account=is_test)
            return Application.objects.create(
                applicant=user,
                submitted_by_agent=agent_profile,
                full_name=user.full_name,
                email=email,
                origin_country=origin,
                destination_country=destination,
            )

        cls.real_agent = agent("real.agent@example.com", False)
        cls.test_agent = agent("test.agent@example.com", True)
        cls.real_app = student("real.student@example.com", cls.real_agent, False)
        cls.test_app = student("test.student@example.com", cls.test_agent, True)

    def setUp(self):
        self.client.force_login(self.staff)

    def _list(self, name, query=""):
        response = self.client.get(reverse(f"admin:{name}_changelist") + query)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_working_screens_hide_test_data(self):
        page = self._list("applications_agentapplication")
        self.assertIn(self.real_app.reference, page)
        self.assertNotIn(self.test_app.reference, page)

        for name in ("partners_agentprofile", "applications_agentapplications", "accounts_user"):
            page = self._list(name)
            self.assertIn("real.agent", page)
            self.assertNotIn("test.agent", page)

    def test_test_accounts_section_shows_only_test_data(self):
        page = self._list("testaccounts_testapplication")
        self.assertIn(self.test_app.reference, page)
        self.assertNotIn(self.real_app.reference, page)

        page = self._list("testaccounts_testagent")
        self.assertIn("test.agent", page)
        self.assertNotIn("real.agent", page)

        page = self._list("testaccounts_testuser")
        self.assertIn("test.student@example.com", page)
        self.assertNotIn("real.student@example.com", page)

    def test_drill_down_and_record_pages_still_open(self):
        page = self._list("applications_agentapplication", f"?agent={self.test_agent.pk}")
        self.assertIn(self.test_app.reference, page)

        response = self.client.get(reverse("admin:applications_agentapplication_change", args=[self.test_app.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("admin:applications_agentapplication_download", args=[self.test_app.pk]))
        self.assertEqual(response.status_code, 200)

    def test_no_email_reaches_a_test_account(self):
        mail.outbox = []
        send_async_email("Hi", "Hi", "<p>Hi</p>", ["TEST.student@example.com"], wait=True)
        self.assertEqual(mail.outbox, [])

        send_async_email(
            "Hi", "Hi", "<p>Hi</p>", ["test.student@example.com", "real.student@example.com"], wait=True
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["real.student@example.com"])

    def test_agent_filter_lists_only_its_own_side(self):
        page = self._list("applications_agentapplication")
        self.assertNotIn("test.agent@example.com agency", page)
        self.assertNotIn(">test.agent<", page)

        page = self._list("testaccounts_testapplication")
        self.assertNotIn(">real.agent<", page)
