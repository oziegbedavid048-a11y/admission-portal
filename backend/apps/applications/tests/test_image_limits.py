"""Pictures and PDFs are processed without letting one upload exhaust memory."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.applications import compression
from apps.applications.models import Document

from .factories import make_application, make_user


def png(width, height):
    out = io.BytesIO()
    Image.new("L", (width, height), 255).save(out, "PNG")
    return out.getvalue()


def jpeg(width, height, orientation=None):
    out = io.BytesIO()
    image = Image.new("RGB", (width, height), (200, 30, 30))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    image.save(out, "JPEG", quality=95, exif=exif.tobytes())
    return out.getvalue()


class ImageLimitTests(TestCase):
    def setUp(self):
        self.user = make_user("applicant@example.com")
        self.application = make_application(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = f"/api/applications/{self.application.reference}/documents/"

    def upload(self, name, data, content_type):
        return self.client.post(
            self.url,
            {"kind": "passport", "name": "Passport", "file": SimpleUploadedFile(name, data, content_type=content_type)},
            format="multipart",
        )

    def test_decompression_bomb_png_is_refused(self):
        # 9,000 x 9,000 is 81 megapixels: a small file that would unpack to
        # hundreds of megabytes.
        bomb = png(9000, 9000)
        self.assertLess(len(bomb), 1024 * 1024)
        response = self.upload("scan.png", bomb, "image/png")
        self.assertEqual(response.status_code, 400)
        self.assertIn("too large", str(response.json()))
        self.assertFalse(Document.objects.exists())

    def test_a_normal_phone_photo_is_accepted_and_shrunk(self):
        response = self.upload("photo.jpg", jpeg(4000, 3000), "image/jpeg")
        self.assertEqual(response.status_code, 201, response.content)
        stored = Document.objects.get()
        with Image.open(stored.file) as image:
            self.assertLessEqual(max(image.size), 2000)

    def test_rotated_photo_is_turned_upright(self):
        # Orientation 6: stored landscape, meant to be shown portrait.
        result = compression._compress_image(jpeg(3000, 2000, orientation=6), ".jpg", "document")
        data, extension = result
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
        self.assertEqual(extension, ".jpg")
        self.assertGreater(height, width)

    def test_pdf_compression_still_works_on_current_pypdf(self):
        out = io.BytesIO()
        Image.new("RGB", (2500, 3500), (255, 255, 255)).save(out, "PDF")
        smaller = compression._compress_pdf(out.getvalue())
        self.assertTrue(smaller.startswith(b"%PDF-"))

    def test_very_long_pdf_is_left_as_sent(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(compression.MAX_PDF_PAGES + 1):
            writer.add_blank_page(width=200, height=200)
        out = io.BytesIO()
        writer.write(out)
        self.assertIsNone(compression._compress_pdf(out.getvalue()))
