"""Reference data: where applicants come from, where they go, and who teaches them.

This is the data that used to live in ``js/data.js``. It is reference data
rather than user data, so it is seeded with ``manage.py seed_catalog`` and is
readable without authentication.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class OriginCountry(models.Model):
    """A country an applicant can apply from, and the currency they pay in.

    ``ngn_per_unit`` is how many Naira one unit of the local currency is worth,
    so the fee shown is ``APPLICATION_FEE_NGN / ngn_per_unit``. These rates are
    indicative reference values held so the product runs without an FX
    provider; wire them to a live source before taking real money, and keep the
    Naira figure on screen beside the converted one so drift stays visible.
    """

    name = models.CharField(max_length=80, unique=True)
    currency = models.CharField(max_length=8)
    symbol = models.CharField(max_length=8)
    ngn_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="How many Naira one unit of this currency is worth.",
    )

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "origin countries"

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def convert_from_ngn(self, amount_ngn):
        return (Decimal(amount_ngn) / self.ngn_per_unit).quantize(Decimal("0.01"))


class DestinationCountry(models.Model):
    """A study destination, which decides which institutions show in step 3."""

    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=4)
    currency = models.CharField(max_length=8)
    currency_symbol = models.CharField(max_length=8, blank=True)
    is_european = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name_plural = "destination countries"

    def __str__(self):
        return self.name


class Institution(models.Model):
    """A partner university or business school."""

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=200)
    country = models.ForeignKey(
        DestinationCountry, on_delete=models.CASCADE, related_name="institutions"
    )
    location = models.CharField(max_length=160, blank=True)
    tagline = models.CharField(max_length=400, blank=True)
    badge = models.CharField(max_length=80, blank=True, default="Partner School")
    currency = models.CharField(max_length=8, default="EUR")
    application_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Charged once per institution, never per course. 0 means fee-free.",
    )
    tuition_summary = models.CharField(max_length=200, blank=True)
    features = models.JSONField(default=list, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name

    @property
    def is_fee_free(self):
        return self.application_fee == 0


class Program(models.Model):
    """A course an applicant can pick. Up to two per institution."""

    class Level(models.TextChoices):
        BACHELORS = "bachelors", "Bachelor's Degrees"
        MASTERS = "masters", "Masters & MBA"
        PHD = "phd", "PhD & Doctoral Programs"
        DIPLOMAS = "diplomas", "Diplomas & Certificates"
        OTHER = "other", "Other Academic Programs"

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="programs"
    )
    name = models.CharField(max_length=250)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.OTHER)
    duration = models.CharField(max_length=60, blank=True)
    qualification_level = models.CharField(
        max_length=80, blank=True, help_text="e.g. Level 7 (RNCP41354)"
    )
    tuition = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    intake = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=300, blank=True)
    scholarship = models.CharField(max_length=300, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name = "course"
        verbose_name_plural = "courses"
        constraints = [
            models.UniqueConstraint(
                fields=("institution", "name"), name="unique_program_per_institution"
            )
        ]

    def __str__(self):
        return f"{self.name} · {self.institution.name}"


class FaqItem(models.Model):
    question = models.CharField(max_length=250)
    answer = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order",)
        verbose_name = "landing page question"
        verbose_name_plural = "landing page questions"

    def __str__(self):
        return self.question


class CourseImport(Program):
    """A stand-in so the paste importer has a place on the admin index.

    It stores nothing of its own. Courses, schools and countries all reach the
    catalogue through this one screen, so the index lists it instead of the
    three models it writes to.
    """

    class Meta:
        proxy = True
        verbose_name = "Add course"
        verbose_name_plural = "Add course"
