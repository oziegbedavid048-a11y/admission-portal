"""Applicants see school codes, not names, until they pay the application fee."""

import re
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.models import Application
from apps.applications.tests.factories import make_user
from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program
from apps.payments.models import Payment

SCHOOL = "Maple Ridge College"


class SchoolCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        OriginCountry.objects.create(name="Nigeria", currency="NGN", symbol="N", ngn_per_unit=Decimal("1"))
        self.canada = DestinationCountry.objects.update_or_create(name="Canada", defaults={"code": "CA", "currency": "CAD"})[0]
        self.school = Institution.objects.create(
            slug="maple-ridge-college",
            name=SCHOOL,
            country=self.canada,
            location="Toronto",
            tagline=f"{SCHOOL}, in the heart of Toronto",
            application_fee=Decimal("150"),
            currency="CAD",
        )
        self.course = Program.objects.create(
            institution=self.school, name="Business Administration", scholarship=f"{SCHOOL} entrance award"
        )
        self.applicant = make_user("ada@example.com")
        self.agent = make_user("agent@example.com", role=User.Role.AGENT)
        mock.patch("apps.accounts.emails.send_application_received_email").start()
        self.addCleanup(mock.patch.stopall)

    def client_for(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    # ── The code ────────────────────────────────────────────────────────

    def test_every_school_gets_a_country_code_not_taken_from_its_name(self):
        self.assertRegex(self.school.code, r"^CA-\d{3}$")
        other = Institution.objects.create(slug="other", name="Other", country=self.canada)
        self.assertNotEqual(other.code, self.school.code)

    # ── The catalogue ───────────────────────────────────────────────────

    def test_applicants_and_visitors_see_the_code_and_nothing_that_names_the_school(self):
        for client in (self.client_for(), self.client_for(self.applicant)):
            body = client.get("/api/catalog/institutions/", {"country": "Canada"}).content.decode()
            self.assertNotIn(SCHOOL, body)
            self.assertNotIn("maple-ridge", body)
            self.assertNotIn("Toronto", body)
            self.assertIn(self.school.code, body)
            self.assertIn("Business Administration", body)
            self.assertIn("150", body)  # the fee still shows

    def test_agents_still_see_the_real_name(self):
        body = self.client_for(self.agent).get("/api/catalog/institutions/", {"country": "Canada"}).content.decode()
        self.assertIn(SCHOOL, body)
        self.assertIn("Toronto", body)

    def test_an_applicant_cannot_find_the_code_by_searching_or_looking_up_the_name(self):
        client = self.client_for(self.applicant)
        self.assertEqual(client.get("/api/catalog/institutions/", {"search": "Maple"}).json(), [])
        self.assertEqual(client.get("/api/catalog/institutions/maple-ridge-college/").status_code, 404)
        self.assertEqual(client.get(f"/api/catalog/institutions/{self.school.code}/").json()["name"], self.school.code)
        rows = client.get("/api/catalog/programs/", {"search": "Maple"}).json()["results"]
        self.assertEqual(rows, [])

    def test_course_rows_name_the_school_by_code_for_applicants(self):
        rows = self.client_for(self.applicant).get("/api/catalog/programs/", {"country": "Canada"}).json()["results"]
        self.assertEqual(rows[0]["institution"], self.school.code)
        self.assertEqual(rows[0]["location"], "")
        self.assertNotIn(SCHOOL, str(rows))
        agent_rows = self.client_for(self.agent).get("/api/catalog/programs/", {"country": "Canada"}).json()["results"]
        self.assertEqual(agent_rows[0]["institution"], SCHOOL)

    def test_the_fee_quote_works_by_code_and_does_not_name_the_school(self):
        client = self.client_for(self.applicant)
        quote = client.get("/api/catalog/fee-quote/", {"institution": self.school.code}).json()
        self.assertFalse(quote["indicative"])
        self.assertEqual(quote["institution"], self.school.code)
        by_slug = client.get("/api/catalog/fee-quote/", {"institution": "maple-ridge-college"}).json()
        self.assertTrue(by_slug["indicative"])  # a name does not unlock the school's quote

    # ── The applicant's own file ────────────────────────────────────────

    def apply(self):
        payload = {
            "full_name": "Ada Obi", "email": "ada@example.com", "phone": "+2348000000000",
            "origin_country": "Nigeria", "destination_country": "Canada", "previous_schools": "Lagos High",
            "qualification": "SSCE / High School", "year_graduated": 2020, "grade_gpa": "B",
            "institution": self.school.code, "program_ids": [self.course.id],
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.applicant).post("/api/applications/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(reference=response.data["reference"])

    def test_the_name_is_hidden_on_the_application_until_the_fee_is_paid(self):
        application = self.apply()
        client = self.client_for(self.applicant)
        before = client.get(f"/api/applications/{application.reference}/").content.decode()
        self.assertNotIn(SCHOOL, before)
        self.assertIn(self.school.code, before)

        Payment.objects.create(
            application=application, amount=Decimal("200000"), amount_ngn=Decimal("200000"),
            currency="NGN", status=Payment.Status.PAID,
        )
        after = client.get(f"/api/applications/{application.reference}/").json()
        self.assertEqual(after["institution"]["name"], SCHOOL)

    def test_a_first_part_payment_also_reveals_the_name(self):
        application = self.apply()
        Payment.objects.create(
            application=application, amount=Decimal("100000"), amount_ngn=Decimal("100000"),
            currency="NGN", status=Payment.Status.PART_PAID,
        )
        data = self.client_for(self.applicant).get(f"/api/applications/{application.reference}/").json()
        self.assertEqual(data["institution"]["name"], SCHOOL)

    def test_the_confirmation_email_uses_the_code_before_payment(self):
        from apps.accounts.emails import _school_for

        application = self.apply()
        self.assertEqual(_school_for(application, False), self.school.code)
        self.assertEqual(_school_for(application, True), SCHOOL)
        self.assertTrue(re.match(r"^CA-\d{3}$", _school_for(application, False)))
