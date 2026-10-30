"""The visas, offer letters and office photo first shown on the home page.

The images were cropped and redacted before they were added (names, passport
and document numbers, addresses, IDs and machine-readable lines blurred), and
are read from apps/catalog/data/landing_reviews. From here on, the desk adds
more in the admin with the blur tool.
"""

from pathlib import Path

from django.core.files.base import ContentFile
from django.db import migrations

FOLDER = Path(__file__).resolve().parent.parent / "data" / "landing_reviews"

CANADA_2023 = "Canada · 2023"
SHERIDAN = "Sheridan College, Canada · ${} scholarship"

REVIEWS = [
    ("office-1.webp", "photo", "Visa collected", "Gabstep office, Nigeria", "center"),
    ("visa-1.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-1.webp", "offer", "Welding and Fabrication", SHERIDAN.format("2,000"), "top"),
    ("visa-3.webp", "visa", "Work permit visa", CANADA_2023, "top"),
    ("offer-5.webp", "offer", "Interior Decorating", SHERIDAN.format("3,000"), "top"),
    ("visa-2.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-2.webp", "offer", "Healthcare Administration", SHERIDAN.format("1,000"), "top"),
    ("visa-5.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-7.webp", "offer", "Social Service Worker", SHERIDAN.format("3,000"), "top"),
    ("visa-4.webp", "visa", "Visitor visa", CANADA_2023, "top"),
    ("offer-3.webp", "offer", "Mechanical Technician", SHERIDAN.format("2,000"), "top"),
    ("visa-7.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-4.webp", "offer", "Supply Chain Management", SHERIDAN.format("2,000"), "top"),
    ("visa-6.webp", "visa", "Student visa", "Canada · 2021", "top"),
    ("offer-6.webp", "offer", "Personal Support Worker", SHERIDAN.format("2,000"), "top"),
    ("visa-8.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-8.webp", "offer", "Healthcare Administration", SHERIDAN.format("3,000"), "top"),
    ("visa-9.webp", "visa", "Student visa", CANADA_2023, "top"),
    ("offer-9.webp", "offer", "Welding and Fabrication", SHERIDAN.format("2,000"), "top"),
]


def add_reviews(apps, schema_editor):
    LandingReview = apps.get_model("catalog", "LandingReview")
    if LandingReview.objects.exists():
        return
    for order, (file, kind, title, detail, focus) in enumerate(REVIEWS, 1):
        review = LandingReview(kind=kind, title=title, detail=detail, focus=focus, display_order=order * 10)
        review.image.save(file, ContentFile((FOLDER / file).read_bytes()), save=False)
        review.save()


def remove_reviews(apps, schema_editor):
    LandingReview = apps.get_model("catalog", "LandingReview")
    for review in LandingReview.objects.all():
        if review.image:
            review.image.storage.delete(review.image.name)
        review.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0014_landingreview"),
        # The images are written through the database file storage.
        ("filestore", "0001_initial"),
    ]

    operations = [migrations.RunPython(add_reviews, remove_reviews)]
