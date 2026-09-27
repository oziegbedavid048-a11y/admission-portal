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


def ngn_per_unit(currency):
    """How many Naira one unit of `currency` is worth.

    The application fee is not the same everywhere: most partners charge a flat
    Naira amount, but UCAM charges 150 EUR, and the card is always debited in
    Naira. So a fee has to be convertible from whatever the school quotes it in.

    The rate comes from the same table the applicant's own currency uses, keyed
    by currency rather than by country because several countries share the euro.
    Unknown currency raises rather than guessing: charging the wrong amount is
    worse than refusing to quote.
    """
    code = (currency or "NGN").upper()
    if code == "NGN":
        return Decimal("1")
    row = OriginCountry.objects.filter(currency__iexact=code).first()
    if row is None:
        raise ValueError(
            f"No exchange rate on file for {code}. Add a country using it under "
            "Exchange rates before quoting a fee in that currency."
        )
    return row.ngn_per_unit


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
    # The currency the APPLICATION FEE is quoted in, which is not always the
    # school's own. Most partners set their fee in Naira; UCAM sets it at 150
    # EUR. Kept apart from `currency` above, which is what the school quotes its
    # tuition and its deposit in, because conflating the two made every euro
    # tuition figure render as Naira.
    application_fee_currency = models.CharField(max_length=8, default="NGN")
    application_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Charged once per institution, never per course. 0 means fee-free.",
    )
    tuition_summary = models.CharField(max_length=200, blank=True)

    # The deposit a school asks for on top of the application fee. Recorded so
    # the applicant is told what is coming; it is not collected here, because it
    # is paid to the school rather than to us.
    tuition_deposit_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Share of the total tuition taken as a deposit, e.g. 50 for half.",
    )
    tuition_deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "A flat deposit in this school's currency, for schools that ask for "
            "a fixed sum rather than a share. Leave at 0 when a percentage is used."
        ),
    )
    features = models.JSONField(default=list, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name) or "school"
            slug = base_slug
            counter = 1
            while Institution.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_fee_free(self):
        return self.application_fee == 0

    @property
    def application_fee_ngn(self):
        """This school's application fee in Naira, which is what is charged.

        Every school sets its own. Quoting one school's fee against another is
        the mistake this property exists to make impossible: there is one place
        the number comes from, and it is the row for the school being applied to.
        """
        if self.application_fee == 0:
            return Decimal("0.00")
        rate = ngn_per_unit(self.application_fee_currency)
        return (Decimal(self.application_fee) * rate).quantize(Decimal("0.01"))

    @property
    def deposit_note(self):
        """How the school describes its tuition deposit, or empty if it has none.

        Quoted in the school's own currency, which is what its tuition is in,
        not in whatever the application fee happens to be denominated in.
        """
        if self.tuition_deposit_amount:
            return f"{self.currency} {self.tuition_deposit_amount:,.0f} tuition deposit"
        if self.tuition_deposit_percent:
            percent = self.tuition_deposit_percent.normalize()
            return f"{percent:f}% of total tuition as a deposit"
        return ""


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
