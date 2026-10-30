"""Landing page review images: the public list and the admin's blur-and-save flow."""

import base64
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import LandingReview
from apps.filestore.models import StoredFile


def data_url(size=(400, 300)):
    out = io.BytesIO()
    Image.new("RGB", size, "#3a7").save(out, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def pdf_bytes():
    from reportlab.pdfgen import canvas

    out = io.BytesIO()
    page = canvas.Canvas(out)
    page.drawString(72, 720, "Letter of Acceptance")
    page.save()
    return out.getvalue()


class LandingReviewApiTests(TestCase):
    def test_the_first_reviews_are_listed_in_order_with_full_image_links(self):
        response = APIClient().get("/api/catalog/landing-reviews/")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual(len(items), 19)
        self.assertEqual(items[0]["title"], "Visa collected")
        self.assertTrue(items[0]["image"].startswith("http://testserver/media/landing-reviews/"))
        self.assertEqual({item["kind"] for item in items}, {"visa", "offer", "photo"})

    def test_a_hidden_review_is_not_listed(self):
        LandingReview.objects.filter(title="Visa collected").update(is_active=False)
        titles = [item["title"] for item in APIClient().get("/api/catalog/landing-reviews/").json()]
        self.assertNotIn("Visa collected", titles)

    def test_the_stored_images_are_served(self):
        review = LandingReview.objects.first()
        response = self.client.get(review.image.url)
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/webp"))


class LandingReviewAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(email="desk@example.com", password="pw-123456")
        self.client.force_login(self.staff)
        self.add_url = reverse("admin:catalog_landingreview_add")

    def post(self, **overrides):
        body = {
            "kind": "visa",
            "title": "Student visa",
            "detail": "Canada · 2026",
            "focus": "top",
            "display_order": "5",
            "is_active": "on",
            "redacted": data_url(),
            "blur_count": "2",
            **overrides,
        }
        return self.client.post(self.add_url, body)

    def test_the_blurred_picture_is_saved_small_and_the_original_is_not(self):
        files_before = StoredFile.objects.count()
        response = self.post(source=SimpleUploadedFile("passport.jpg", b"original bytes", content_type="image/jpeg"))
        self.assertEqual(response.status_code, 302, response.content[:2000])
        review = LandingReview.objects.get(detail="Canada · 2026")
        self.assertTrue(review.image.name.endswith(".webp"))
        self.assertEqual(StoredFile.objects.count(), files_before + 1)
        self.assertFalse(StoredFile.objects.filter(name__icontains="passport").exists())
        stored = StoredFile.objects.get(name=review.image.name)
        self.assertEqual(Image.open(io.BytesIO(bytes(stored.content))).format, "WEBP")

    def test_without_an_image_nothing_is_saved(self):
        response = self.post(redacted="")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose an image or PDF")
        self.assertFalse(LandingReview.objects.filter(detail="Canada · 2026").exists())

    def test_nothing_blurred_needs_the_nothing_private_tick(self):
        response = self.post(blur_count="0")
        self.assertContains(response, "nothing private")
        self.assertFalse(LandingReview.objects.filter(detail="Canada · 2026").exists())
        self.assertEqual(self.post(blur_count="0", nothing_private="on").status_code, 302)

    def test_a_picture_that_is_not_an_image_is_refused(self):
        response = self.post(redacted="data:image/jpeg;base64," + base64.b64encode(b"<html>").decode())
        self.assertContains(response, "could not be read")
        self.assertFalse(LandingReview.objects.filter(detail="Canada · 2026").exists())

    def test_a_wide_picture_is_stored_at_most_960_pixels_wide(self):
        self.post(redacted=data_url((2400, 1200)))
        review = LandingReview.objects.get(detail="Canada · 2026")
        stored = StoredFile.objects.get(name=review.image.name)
        self.assertEqual(Image.open(io.BytesIO(bytes(stored.content))).size, (960, 480))

    def test_editing_without_a_new_picture_keeps_the_image(self):
        review = LandingReview.objects.first()
        name = review.image.name
        url = reverse("admin:catalog_landingreview_change", args=[review.pk])
        response = self.client.post(url, {
            "kind": review.kind, "title": "Renamed", "detail": review.detail, "focus": review.focus,
            "display_order": "1", "is_active": "on", "redacted": "", "blur_count": "0",
        })
        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        self.assertEqual((review.title, review.image.name), ("Renamed", name))

    def test_a_new_picture_on_edit_replaces_and_removes_the_old_file(self):
        review = LandingReview.objects.first()
        old = review.image.name
        url = reverse("admin:catalog_landingreview_change", args=[review.pk])
        self.client.post(url, {
            "kind": review.kind, "title": review.title, "detail": review.detail, "focus": review.focus,
            "display_order": "1", "is_active": "on", "redacted": data_url(), "blur_count": "1",
        })
        review.refresh_from_db()
        self.assertNotEqual(review.image.name, old)
        self.assertFalse(StoredFile.objects.filter(name=old).exists())

    def test_the_pdf_preview_shows_the_first_page_and_keeps_nothing(self):
        files_before = StoredFile.objects.count()
        response = self.client.post(
            reverse("admin:catalog_landingreview_pdf_preview"),
            {"file": SimpleUploadedFile("letter.pdf", pdf_bytes(), content_type="application/pdf")},
        )
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/png"))
        self.assertEqual(Image.open(io.BytesIO(response.content)).format, "PNG")
        self.assertEqual(StoredFile.objects.count(), files_before)

    def test_the_pdf_preview_refuses_a_file_that_is_not_a_pdf(self):
        response = self.client.post(
            reverse("admin:catalog_landingreview_pdf_preview"),
            {"file": SimpleUploadedFile("letter.pdf", b"not a pdf", content_type="application/pdf")},
        )
        self.assertEqual(response.status_code, 400)

    def test_the_pdf_preview_is_for_staff_only(self):
        self.client.logout()
        response = self.client.post(
            reverse("admin:catalog_landingreview_pdf_preview"),
            {"file": SimpleUploadedFile("letter.pdf", pdf_bytes(), content_type="application/pdf")},
        )
        self.assertNotEqual(response.status_code, 200)

    def test_the_add_page_carries_the_blur_tool(self):
        response = self.client.get(self.add_url)
        self.assertContains(response, 'id="lr-blur"')
        self.assertContains(response, "admin/landing_reviews/blur.js")
