"""An applicant may pick up to two courses at one school, under one fee, and
may apply to further schools, each as its own application with its own fee."""

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.applications.models import Application
from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program
from apps.payments.views import quote_for

from .factories import make_user


class MultipleApplicationsTests(TestCase):
    def setUp(self):
        OriginCountry.objects.create(
            name="Nigeria", currency="NGN", symbol="N", ngn_per_unit=Decimal("1")
        )
        self.france = DestinationCountry.objects.create(name="France", code="FR", currency="EUR")
        self.school_a = Institution.objects.create(
            slug="school-a", name="School A", country=self.france, application_fee=Decimal("200000")
        )
        self.school_b = Institution.objects.create(
            slug="school-b", name="School B", country=self.france, application_fee=Decimal("150000")
        )
        self.a1 = Program.objects.create(institution=self.school_a, name="Course A1")
        self.a2 = Program.objects.create(institution=self.school_a, name="Course A2")
        self.a3 = Program.objects.create(institution=self.school_a, name="Course A3")
        self.b1 = Program.objects.create(institution=self.school_b, name="Course B1")

        self.user = make_user("ada@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        # The confirmation email is not what these tests are about.
        patcher = mock.patch("apps.accounts.emails.send_application_received_email")
        patcher.start()
        self.addCleanup(patcher.stop)

    def payload(self, school, program_ids):
        return {
            "full_name": "Ada Obi",
            "email": "ada@example.com",
            "phone": "+2348000000000",
            "origin_country": "Nigeria",
            "destination_country": "France",
            "previous_schools": "Lagos High",
            "qualification": "SSCE / High School",
            "year_graduated": 2020,
            "grade_gpa": "B",
            "institution": school.slug,
            "program_ids": program_ids,
        }

    def apply(self, school, program_ids):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                "/api/applications/", self.payload(school, program_ids), format="json"
            )

    # ── Several courses, one school, one application ──

    def test_two_courses_at_one_school_make_one_application(self):
        response = self.apply(self.school_a, [self.a1.id, self.a2.id])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Application.objects.filter(applicant=self.user).count(), 1)
        application = Application.objects.get(reference=response.data["reference"])
        self.assertEqual(
            sorted(application.programs.values_list("id", flat=True)), sorted([self.a1.id, self.a2.id])
        )

    def test_the_fee_is_charged_once_whatever_the_number_of_courses(self):
        one = self.apply(self.school_a, [self.a1.id])
        Application.objects.filter(reference=one.data["reference"]).update(
            status=Application.Status.REJECTED
        )
        two = self.apply(self.school_a, [self.a1.id, self.a2.id])
        single = quote_for(Application.objects.get(reference=one.data["reference"]))
        double = quote_for(Application.objects.get(reference=two.data["reference"]))
        self.assertEqual(single["total_ngn"], double["total_ngn"])

    def test_more_than_two_courses_is_refused(self):
        response = self.apply(self.school_a, [self.a1.id, self.a2.id, self.a3.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn("program_ids", response.data)
        self.assertFalse(Application.objects.exists())

    def test_the_same_course_twice_counts_once(self):
        response = self.apply(self.school_a, [self.a1.id, self.a1.id])
        self.assertEqual(response.status_code, 201, response.data)
        application = Application.objects.get(reference=response.data["reference"])
        self.assertEqual(list(application.programs.values_list("id", flat=True)), [self.a1.id])

    def test_no_course_is_never_filled_in_for_the_applicant(self):
        response = self.apply(self.school_a, [])
        self.assertEqual(response.status_code, 400)
        self.assertIn("program_ids", response.data)
        self.assertFalse(Application.objects.exists())

    def test_a_course_from_another_school_is_refused(self):
        response = self.apply(self.school_a, [self.a1.id, self.b1.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn("program_ids", response.data)
        self.assertFalse(Application.objects.exists())

    # ── Further schools, each its own application ──

    def test_a_second_school_is_a_second_application_with_its_own_fee(self):
        first = self.apply(self.school_a, [self.a1.id])
        second = self.apply(self.school_b, [self.b1.id])
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(first.data["reference"], second.data["reference"])

        quote_a = quote_for(Application.objects.get(reference=first.data["reference"]))
        quote_b = quote_for(Application.objects.get(reference=second.data["reference"]))
        self.assertNotEqual(quote_a["total_ngn"], quote_b["total_ngn"])

    def test_a_paid_application_does_not_stop_a_new_one(self):
        from apps.payments.models import Payment

        first = self.apply(self.school_a, [self.a1.id])
        application = Application.objects.get(reference=first.data["reference"])
        Payment.objects.create(
            application=application,
            amount=Decimal("200000"),
            amount_ngn=Decimal("200000"),
            currency="NGN",
            status=Payment.Status.PAID,
        )
        second = self.apply(self.school_b, [self.b1.id])
        self.assertEqual(second.status_code, 201, second.data)

    def test_the_same_school_twice_is_refused(self):
        self.apply(self.school_a, [self.a1.id])
        again = self.apply(self.school_a, [self.a2.id])
        self.assertEqual(again.status_code, 400)
        self.assertIn("institution", again.data)
        self.assertEqual(Application.objects.filter(applicant=self.user).count(), 1)

    def test_a_rejected_school_may_be_applied_to_again(self):
        first = self.apply(self.school_a, [self.a1.id])
        Application.objects.filter(reference=first.data["reference"]).update(
            status=Application.Status.REJECTED
        )
        again = self.apply(self.school_a, [self.a2.id])
        self.assertEqual(again.status_code, 201, again.data)

    # ── Reading them back ──

    def test_the_applicant_can_list_and_open_each_application(self):
        first = self.apply(self.school_a, [self.a1.id, self.a2.id]).data["reference"]
        second = self.apply(self.school_b, [self.b1.id]).data["reference"]

        listing = self.client.get("/api/applications/mine/all/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual({row["reference"] for row in listing.data}, {first, second})
        row_a = next(row for row in listing.data if row["reference"] == first)
        self.assertEqual(row_a["institution_slug"], "school-a")
        self.assertEqual(sorted(row_a["courses"]), ["Course A1", "Course A2"])

        opened = self.client.get("/api/applications/mine/", {"reference": first})
        self.assertEqual(opened.data["reference"], first)
        opened = self.client.get("/api/applications/mine/", {"reference": second})
        self.assertEqual(opened.data["reference"], second)

    def test_another_applicants_reference_is_never_opened(self):
        own = self.apply(self.school_a, [self.a1.id]).data["reference"]
        stranger = make_user("other@example.com")
        foreign = Application.objects.create(
            applicant=stranger,
            full_name="Other",
            email="other@example.com",
            origin_country=OriginCountry.objects.get(name="Nigeria"),
            destination_country=self.france,
            institution=self.school_b,
        )
        opened = self.client.get("/api/applications/mine/", {"reference": foreign.reference})
        self.assertEqual(opened.data["reference"], own)
        listing = self.client.get("/api/applications/mine/all/")
        self.assertEqual([row["reference"] for row in listing.data], [own])
