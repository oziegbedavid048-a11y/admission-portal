"""List endpoints cost the same number of queries for one row as for many.

A table that asks the database once per row (an N+1) is fast with three test
records and slow with three hundred real ones. Each test below loads a page
with one row, then with several, and the query count must not grow.
"""

from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Document, Letter
from apps.applications.tests.factories import make_application, make_user
from apps.catalog.models import DestinationCountry, Institution, Program
from apps.partners.models import AgentProfile, Commission, SupervisorBonus, SupervisorProfile, Wallet
from apps.payments.models import Payment


class QueryCountTests(TestCase):
    def setUp(self):
        self.staff = make_user("desk@example.com", role=User.Role.STAFF, is_staff=True)
        self.manager_user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        self.manager = SupervisorProfile.objects.create(user=self.manager_user)
        self.agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        self.agent = AgentProfile.objects.create(user=self.agent_user, supervisor=self.manager)
        Wallet.objects.create(agent=self.agent)
        self.applicant = make_user("student@example.com")
        canada, _ = DestinationCountry.objects.get_or_create(name="Canada", defaults={"code": "CA", "currency": "CAD"})
        self.school = Institution.objects.create(slug="maple", name="Maple College", country=canada)
        self.course = Program.objects.create(institution=self.school, name="Nursing")
        self.count = 0

    def add_rows(self, n):
        for _ in range(n):
            self.count += 1
            student = make_user(f"s{self.count}@example.com")
            for owner, agent in ((student, self.agent), (self.applicant, None)):
                application = make_application(owner, institution=self.school, submitted_by_agent=agent)
                application.programs.add(self.course)
                application.build_default_stages()
                Payment.objects.create(
                    application=application, amount=Decimal("100"), amount_ngn=Decimal("100"), status="paid"
                )
                Document.objects.create(application=application, name="Passport", file=ContentFile(b"%PDF-1", name="p.pdf"))
                Letter.objects.create(
                    application=application, title="Offer", is_published=True, file=ContentFile(b"%PDF-1", name="l.pdf")
                )
                if agent is not None:
                    Commission.objects.create(agent=agent, application=application, kind="registration")
                    SupervisorBonus.objects.create(supervisor=self.manager, agent=agent, application=application)

    def queries(self, user, url):
        client = APIClient()
        client.force_authenticate(user)
        # The first request also fills one-off caches; only a repeat is counted.
        client.get(url)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, f"{url}: {response.content[:300]}")
        return len(captured)

    def assert_flat(self, user, url):
        self.add_rows(1)
        one = self.queries(user, url)
        self.add_rows(3)
        many = self.queries(user, url)
        self.assertEqual(one, many, f"{url} grew from {one} to {many} queries with more rows")

    def test_applicant_application_list(self):
        self.assert_flat(self.applicant, "/api/applications/")

    def test_applicant_application_summaries(self):
        self.assert_flat(self.applicant, "/api/applications/mine/all/")

    def test_staff_application_list(self):
        self.assert_flat(self.staff, "/api/applications/")

    def test_agent_application_list(self):
        self.assert_flat(self.agent_user, "/api/applications/")

    def test_agent_students(self):
        self.assert_flat(self.agent_user, "/api/partners/students/")

    def test_agent_overview(self):
        self.assert_flat(self.agent_user, "/api/partners/overview/")

    def test_agent_letters(self):
        self.assert_flat(self.agent_user, "/api/partners/letters/")

    def test_agent_commissions(self):
        self.assert_flat(self.agent_user, "/api/partners/commissions/")

    def test_agent_wallet_history(self):
        self.assert_flat(self.agent_user, "/api/partners/wallet/history/")

    def test_manager_students(self):
        self.assert_flat(self.manager_user, "/api/supervisors/students/")

    def test_manager_agents(self):
        self.assert_flat(self.manager_user, "/api/supervisors/agents/")

    def test_manager_overview(self):
        self.assert_flat(self.manager_user, "/api/supervisors/overview/")

    def test_manager_bonuses(self):
        self.assert_flat(self.manager_user, "/api/supervisors/bonuses/")
