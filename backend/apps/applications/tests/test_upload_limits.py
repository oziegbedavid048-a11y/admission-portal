"""One person cannot fill the database, and typed countries stay contained."""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.applications import uploads
from apps.applications.models import Document
from apps.catalog.models import DestinationCountry, OriginCountry, ngn_per_unit

from .factories import make_application, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def pdf(name="scan.pdf"):
    return SimpleUploadedFile(name, PDF, content_type="application/pdf")


class UploadLimitTests(TestCase):
    def setUp(self):
        self.user = make_user("applicant@example.com")
        self.application = make_application(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_documents_per_application_are_capped(self):
        for _ in range(uploads.MAX_DOCUMENTS_PER_APPLICATION):
            Document.objects.create(application=self.application, kind="other", name="Extra", file=pdf())
        response = self.client.post(
            f"/api/applications/{self.application.reference}/documents/",
            {"kind": "other", "name": "One more", "file": pdf()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Document.objects.count(), uploads.MAX_DOCUMENTS_PER_APPLICATION)

    def test_draft_files_are_capped_but_replacing_one_is_fine(self):
        url = "/api/applications/draft/files/"
        for i in range(uploads.MAX_FILES_PER_DRAFT):
            response = self.client.post(url, {"slot": f"s{i}", "name": "Doc", "file": pdf()}, format="multipart")
            self.assertEqual(response.status_code, 201, response.content)
        refused = self.client.post(url, {"slot": "extra", "name": "Doc", "file": pdf()}, format="multipart")
        self.assertEqual(refused.status_code, 400)
        replaced = self.client.post(url, {"slot": "s0", "name": "Doc", "file": pdf()}, format="multipart")
        self.assertEqual(replaced.status_code, 201)


class TypedCountryTests(TestCase):
    def setUp(self):
        OriginCountry.objects.create(name="United States", currency="USD", symbol="$", ngn_per_unit=Decimal("1550"))
        DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        self.client = APIClient()
        self.client.force_authenticate(make_user("ada@example.com"))

    def apply(self, origin, destination="Canada"):
        return self.client.post(
            "/api/applications/",
            {
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "phone": "+2348000000000",
                "origin_country": origin,
                "destination_country": destination,
                "previous_schools": "School",
                "qualification": "BSc",
                "year_graduated": 2020,
                "grade_gpa": "4.0",
                "is_custom_course": True,
                "custom_course_name": "Nursing",
            },
            format="json",
        )

    def test_a_new_origin_country_cannot_change_the_dollar_rate(self):
        response = self.apply("Aaa Land")
        self.assertIn(response.status_code, (200, 201), response.content)
        self.assertEqual(OriginCountry.objects.get(name="Aaa Land").currency, "NGN")
        self.assertEqual(ngn_per_unit("USD"), Decimal("1550"))

    def test_a_typed_destination_stays_hidden(self):
        response = self.apply("Nigeria", destination="Atlantis")
        self.assertIn(response.status_code, (200, 201), response.content)
        self.assertFalse(DestinationCountry.objects.get(name="Atlantis").is_active)

    def test_a_country_name_with_markup_or_digits_is_refused(self):
        self.assertEqual(self.apply("<script>x</script>").status_code, 400)
        self.assertEqual(self.apply("Country 123").status_code, 400)
        self.assertFalse(OriginCountry.objects.filter(name__icontains="script").exists())
