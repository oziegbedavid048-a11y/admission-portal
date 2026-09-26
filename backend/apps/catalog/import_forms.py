"""The forms behind the Add Course screen.

Three small forms rather than one large one, because the screen has three jobs:
take the paste, settle where the courses belong, and let every parsed row be
corrected before it is written.
"""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import DestinationCountry, Institution, Program

CURRENCY_SIGNS = {"EUR": "€", "GBP": "£", "USD": "$", "NGN": "₦"}


class PasteForm(forms.Form):
    """Stage one: the block of text, and nothing else."""

    paste = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
                "rows": 16,
                "spellcheck": "false",
                "placeholder": (
                    "Paste the school's course list here.\n\n"
                    "Country: Spain\n"
                    "School: EU Business School Barcelona\n"
                    "City: Barcelona, Spain\n"
                    "\n"
                    "Course\tDuration\tTuition\tIntake\n"
                    "Bachelor of Business Administration\t3 years\t13,500\tOctober & February\n"
                    "Master in Digital Business\t1 year\t14,800\tOctober & January"
                ),
            }
        ),
    )


class DestinationForm(forms.Form):
    """Stage two, upper half: which country, which school, what the fee is."""

    country = forms.ModelChoiceField(
        queryset=DestinationCountry.objects.all(),
        required=False,
        label="Country",
        help_text="Leave empty and name a new one to add a country.",
    )
    new_country_name = forms.CharField(max_length=80, required=False, label="New country")
    new_country_code = forms.CharField(
        max_length=4, required=False, label="Code", help_text="Two letters, e.g. ES, FR, IT."
    )
    new_country_currency = forms.CharField(
        max_length=8, required=False, initial="EUR", label="Country currency"
    )
    new_country_is_european = forms.BooleanField(
        required=False,
        initial=True,
        label="European destination",
        help_text="European institutions ask applicants for a Europass CV.",
    )

    institution = forms.ModelChoiceField(
        queryset=Institution.objects.select_related("country"),
        required=False,
        label="School",
        help_text="Leave empty and name a new one to add a school.",
    )
    new_institution_name = forms.CharField(
        max_length=200, required=False, label="New school"
    )
    location = forms.CharField(max_length=160, required=False, label="City")
    tagline = forms.CharField(
        max_length=400, required=False, label="Tagline", widget=forms.TextInput
    )
    badge = forms.CharField(max_length=80, required=False, label="Badge")
    currency = forms.CharField(max_length=8, required=False, label="Currency")
    application_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        initial=Decimal("0.00"),
        label="Application fee",
        help_text=(
            "Charged once for the school, never per course. 0 marks the school "
            "fee-free: the applicant pays nothing and no registration commission "
            "is earned on their file."
        ),
    )
    tuition_summary = forms.CharField(
        max_length=200,
        required=False,
        label="Tuition range",
        help_text="Left empty, this is worked out from the tuition figures below.",
    )

    def clean(self):
        data = super().clean()
        country = data.get("country")
        new_country = (data.get("new_country_name") or "").strip()
        institution = data.get("institution")
        new_institution = (data.get("new_institution_name") or "").strip()

        if institution is None and not new_institution:
            raise ValidationError({"institution": "Choose a school, or name a new one."})
        if institution and new_institution:
            raise ValidationError(
                {"new_institution_name": "A school is already chosen above. Clear one of them."}
            )
        if country and new_country:
            raise ValidationError(
                {"new_country_name": "A country is already chosen above. Clear one of them."}
            )

        # A new school has to be placed somewhere. An existing one already is.
        if institution is None:
            if country is None and not new_country:
                raise ValidationError({"country": "Choose the country for this school."})
            if country is None and not (data.get("new_country_code") or "").strip():
                raise ValidationError({"new_country_code": "A new country needs its two-letter code."})
            if not (data.get("location") or "").strip():
                raise ValidationError({"location": "Say which city the school is in."})

        return data

    # ── Writing ──────────────────────────────────────────────────────

    def resolve_country(self):
        data = self.cleaned_data
        if data.get("country"):
            return data["country"], False

        name = data["new_country_name"].strip()
        existing = DestinationCountry.objects.filter(name__iexact=name).first()
        if existing:
            return existing, False

        return (
            DestinationCountry.objects.create(
                name=name,
                code=data["new_country_code"].strip().upper(),
                currency=(data.get("new_country_currency") or "EUR").strip().upper(),
                is_european=data.get("new_country_is_european", False),
                display_order=DestinationCountry.objects.count(),
                is_active=True,
            ),
            True,
        )

    def resolve_institution(self):
        """The school these courses belong to, created if it is new.

        An existing school is only changed where a value was actually typed, so
        importing a course list never quietly wipes a school's own details. The
        application fee is the exception: it is a required field on this screen,
        so whatever is in it is meant.
        """
        data = self.cleaned_data
        institution = data.get("institution")

        if institution is None:
            country, country_created = self.resolve_country()
            name = data["new_institution_name"].strip()

            existing = Institution.objects.filter(name__iexact=name).first()
            if existing:
                institution = existing
            else:
                slug = slugify(name)[:60] or "school"
                suffix = 1
                while Institution.objects.filter(slug=slug).exists():
                    suffix += 1
                    slug = f"{slugify(name)[:56]}-{suffix}"

                return (
                    Institution.objects.create(
                        slug=slug,
                        name=name,
                        country=country,
                        location=data.get("location", ""),
                        tagline=data.get("tagline", ""),
                        badge=data.get("badge") or "Partner School",
                        currency=(data.get("currency") or country.currency or "EUR").upper(),
                        application_fee=data["application_fee"],
                        tuition_summary=data.get("tuition_summary", ""),
                        display_order=Institution.objects.filter(country=country).count(),
                        is_active=True,
                    ),
                    True,
                    country_created,
                )

        changed = []
        for field in ("location", "tagline", "badge", "tuition_summary"):
            value = (data.get(field) or "").strip()
            if value and value != getattr(institution, field):
                setattr(institution, field, value)
                changed.append(field)

        currency = (data.get("currency") or "").strip().upper()
        if currency and currency != institution.currency:
            institution.currency = currency
            changed.append("currency")

        if data["application_fee"] != institution.application_fee:
            institution.application_fee = data["application_fee"]
            changed.append("application_fee")

        if changed:
            institution.save(update_fields=changed)

        return institution, False, False


class CourseRowForm(forms.Form):
    """Stage two, lower half: one parsed course, correctable."""

    include = forms.BooleanField(required=False, initial=True, label="Add")
    name = forms.CharField(max_length=250, required=False, label="Course")
    level = forms.ChoiceField(choices=Program.Level.choices, required=False, label="Level")
    duration = forms.CharField(max_length=60, required=False, label="Duration")
    qualification_level = forms.CharField(max_length=120, required=False, label="Accreditation")
    tuition = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False, label="Tuition"
    )
    intake = forms.CharField(max_length=120, required=False, label="Intake")
    scholarship = forms.CharField(max_length=300, required=False, label="Scholarship")
    note = forms.CharField(max_length=300, required=False, label="Fee note")

    def clean(self):
        data = super().clean()
        if data.get("include") and not (data.get("name") or "").strip():
            raise ValidationError({"name": "A course being added needs a name."})
        return data


CourseRowFormSet = forms.formset_factory(CourseRowForm, extra=0)


def summarise_tuition(rows, currency):
    """A headline fee range for the school's card, from the rows being saved."""
    amounts = sorted({row["tuition"] for row in rows if row.get("tuition") is not None})
    if not amounts:
        return ""
    sign = CURRENCY_SIGNS.get(currency.upper(), f"{currency} ")
    if len(amounts) == 1:
        return f"{sign}{amounts[0]:,.0f} / year"
    return f"{sign}{amounts[0]:,.0f} - {sign}{amounts[-1]:,.0f} / year"
