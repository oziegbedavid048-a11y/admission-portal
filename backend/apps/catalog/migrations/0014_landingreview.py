import apps.catalog.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0013_omnes_full_catalogue"),
    ]

    operations = [
        migrations.CreateModel(
            name="LandingReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[("visa", "Visa"), ("offer", "Offer letter"), ("photo", "Photo")],
                        default="visa",
                        max_length=10,
                    ),
                ),
                ("title", models.CharField(help_text='Short, e.g. "Student visa" or "Interior Decorating".', max_length=60)),
                (
                    "detail",
                    models.CharField(
                        help_text='Include the country, e.g. "Canada · 2023" or "Sheridan College, Canada · $2,000 scholarship".',
                        max_length=80,
                    ),
                ),
                ("image", models.FileField(upload_to=apps.catalog.models.landing_review_path)),
                (
                    "focus",
                    models.CharField(
                        choices=[("top", "Top"), ("center", "Middle"), ("bottom", "Bottom")],
                        default="top",
                        help_text="Which part of the image the card shows when it has to crop.",
                        max_length=10,
                    ),
                ),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True, verbose_name="show on landing page")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "landing page review image",
                "verbose_name_plural": "landing page review images",
                "ordering": ("display_order", "-created_at"),
            },
        ),
    ]
