"""The desk can issue a letter from the admin: choose the file, upload, save."""

from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.accounts.models import User
from apps.applications.models import Letter

from .factories import make_application, make_user

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class LetterAdminTests(TestCase):
    def setUp(self):
        self.desk = User.objects.create_superuser(email="desk@example.com", password="Desk-pass-123")
        self.client.force_login(self.desk)
        self.application = make_application(make_user("ada@example.com", full_name="Ada Obi"))

    def add_letter(self, **extra):
        data = {
            "application": self.application.pk,
            "kind": "admission",
            "title": "Admission letter",
            "note": "",
            "issued_at_0": "2026-10-03",
            "issued_at_1": "10:00:00",
            "file": SimpleUploadedFile("letter.pdf", PDF, content_type="application/pdf"),
            "_save": "Save",
        }
        data.update(extra)
        return self.client.post("/admin/applications/letter/add/", data)

    def test_the_add_page_opens(self):
        response = self.client.get("/admin/applications/letter/add/")
        self.assertEqual(response.status_code, 200)

    def test_saving_a_new_letter_publishes_it(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.add_letter()
        self.assertIn(response.status_code, (200, 302), response.content[:2000])
        self.assertEqual(response.status_code, 302, response.content[:3000])
        letter = Letter.objects.get()
        self.assertTrue(letter.is_published)
        self.assertEqual(letter.issued_by, self.desk)

    def test_saving_an_agent_students_letter(self):
        from apps.partners.models import AgentProfile, Wallet

        agent = AgentProfile.objects.create(user=make_user("agent@example.com", role=User.Role.AGENT))
        Wallet.objects.get_or_create(agent=agent)
        self.application.submitted_by_agent = agent
        self.application.save(update_fields=["submitted_by_agent"])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.add_letter()
        self.assertEqual(response.status_code, 302, response.content[:3000])


class SlowPdfTests(TestCase):
    """A PDF that takes too long to rewrite is stored as sent, not left hanging."""

    def test_over_budget_pdf_is_kept_as_sent(self):
        import io

        from pypdf import PdfWriter

        from apps.applications import compression

        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        buffer = io.BytesIO()
        writer.write(buffer)
        original = buffer.getvalue()

        ticks = iter([0.0] + [1000.0] * 50)
        with mock.patch.object(compression.time, "monotonic", lambda: next(ticks)):
            with self.assertRaises(compression._OverBudget):
                compression._compress_pdf(original)

        upload = SimpleUploadedFile("long-letter.pdf", original, content_type="application/pdf")
        field_file = mock.Mock(_committed=False, file=upload)
        field_file.name = "long-letter.pdf"
        ticks = iter([0.0] + [1000.0] * 50)
        with mock.patch.object(compression.time, "monotonic", lambda: next(ticks)):
            compression.compress_upload(field_file)
        upload.seek(0)
        self.assertEqual(field_file.file.read(), original)
