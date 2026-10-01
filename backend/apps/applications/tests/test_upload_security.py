"""Uploaded files can never be served back as a page that runs script."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.applications.models import CorrectionRequest
from apps.filestore.models import StoredFile

from .factories import make_application, make_user

HTML = b"<html><script>alert(document.cookie)</script></html>"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


class CorrectionEvidenceTests(TestCase):
    def setUp(self):
        self.user = make_user("applicant@example.com")
        self.application = make_application(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f"/api/applications/{self.application.reference}/corrections/"

    def post(self, upload):
        return self.client.post(
            self.url,
            {"field": "Name", "corrected_value": "New", "reason": "Typo", "evidence": upload},
            format="multipart",
        )

    def test_html_evidence_is_refused(self):
        response = self.post(SimpleUploadedFile("x.html", HTML, content_type="text/html"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("evidence", response.json())
        self.assertFalse(CorrectionRequest.objects.exists())

    def test_svg_evidence_is_refused(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        response = self.post(SimpleUploadedFile("x.svg", svg, content_type="image/svg+xml"))
        self.assertEqual(response.status_code, 400)

    def test_html_renamed_as_pdf_is_refused(self):
        response = self.post(SimpleUploadedFile("x.pdf", HTML, content_type="application/pdf"))
        self.assertEqual(response.status_code, 400)

    def test_real_pdf_evidence_is_accepted(self):
        response = self.post(SimpleUploadedFile("proof.pdf", PDF, content_type="application/pdf"))
        self.assertEqual(response.status_code, 201, response.content)

    def test_evidence_is_optional(self):
        response = self.client.post(
            self.url, {"field": "Name", "corrected_value": "New", "reason": "Typo"}, format="multipart"
        )
        self.assertEqual(response.status_code, 201, response.content)


class ServeMediaTests(TestCase):
    def store(self, name, content, content_type):
        StoredFile.objects.create(name=name, content=content, size=len(content), content_type=content_type)
        return self.client.get(f"/media/{name}")

    def test_html_row_is_an_inert_download(self):
        # A row stored before upload checks existed, with a hostile type.
        response = self.store("corrections/abc/x.html", HTML, "text/html")
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])

    def test_stored_type_is_ignored_for_pdf_names(self):
        response = self.store("docs/abc/x.pdf", HTML, "text/html")
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_pdf_and_images_still_open_inline(self):
        response = self.store("docs/abc/letter.pdf", PDF, "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertNotIn("sandbox", response["Content-Security-Policy"])
        image = self.store("avatars/abc/me.png", b"\x89PNG\r\n\x1a\n", "image/png")
        self.assertEqual(image["Content-Type"], "image/png")
        self.assertTrue(image["Content-Disposition"].startswith("inline"))

    def test_download_flag_forces_attachment(self):
        StoredFile.objects.create(name="docs/abc/y.pdf", content=PDF, size=len(PDF), content_type="application/pdf")
        response = self.client.get("/media/docs/abc/y.pdf?download=1")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))


class StorageTypeTests(TestCase):
    def test_storage_ignores_the_uploaders_declared_type(self):
        from apps.filestore.storage import DatabaseStorage

        upload = SimpleUploadedFile("evil.txt", b"hello", content_type="text/html")
        name = DatabaseStorage().save("misc/evil.txt", upload)
        self.assertEqual(StoredFile.objects.get(name=name).content_type, "text/plain")
