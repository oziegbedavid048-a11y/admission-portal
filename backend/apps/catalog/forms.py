"""One screen for adding a course.

Putting a course on the platform used to mean three visits: create the country,
create the institution, then come back and create the course. Most of the time
two of those already exist, and when they do not, having to leave the form is
how half-finished institutions end up in the catalogue.

This form does the lot. Pick a country or type a new one, pick a school or type
a new one, fill in the course. Anything already on file is reused and left
alone unless you deliberately fill in a value to change it.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import DestinationCountry, Institution, Program


class AddCourseForm(forms.ModelForm):
    # ── Where ────────────────────────────────────────────────────────
    country = forms.ModelChoiceField(
        queryset=DestinationCountry.objects.all(),
        required=False,
        label="Country",
        help_text="Leave blank and fill in the boxes below to add a new one.",
    )
    new_country_name = forms.CharField(
        max_length=80, required=False, label="Or add a new country"
    )
    new_country_code = forms.CharField(
        max_length=4,
        required=False,
        label="Country code",
        help_text="Two letters, e.g. ES for Spain, FR for France.",
    )
    new_country_currency = forms.CharField(
        max_length=8, required=False, initial="EUR", label="Currency"
    )
    new_country_is_european = forms.BooleanField(
        required=False,
        initial=True,
        label="European destination",
        help_text="European institutions ask applicants for a Europass CV.",
    )

    # ── The school ───────────────────────────────────────────────────
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.select_related("country"),
        required=False,
        label="School",
        help_text="Leave blank and name a new one below.",
    )
    new_institution_name = forms.CharField(
        max_length=200, required=False, label="Or add a new school"
    )
    location = forms.CharField(
        max_length=160,
        required=False,
        label="City",
        help_text="As it is shown to applicants, e.g. Barcelona, Spain.",
    )
    tagline = forms.CharField(
        max_length=400,
        required=False,
        label="Tagline",
        widget=forms.TextInput,
        help_text="One line under the school's name in the picker.",
    )
    badge = forms.CharField(
        max_length=80,
        required=False,
        label="Badge",
        help_text="e.g. Premier Partner, Partner School, Finance Specialist.",
    )
    currency = forms.CharField(
        max_length=8,
        required=False,
        label="Currency",
        help_text="What this school quotes its fees in. Defaults to EUR.",
    )
    application_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="Application fee",
        help_text=(
            "Charged once per school, never per course. Leave at 0 for a "
            "fee-free partner: the applicant then pays nothing and no "
            "registration commission is earned on their file."
        ),
    )
    tuition_summary = forms.CharField(
        max_length=200,
        required=False,
        label="Tuition range",
        help_text="The headline figure on the school's card, e.g. 4,900 to 11,900 EUR / year.",
    )

    class Meta:
        model = Program
        fields = (
            "name",
            "level",
            "duration",
            "qualification_level",
            "tuition",
            "intake",
            "scholarship",
            "note",
            "display_order",
        )
        labels = {
            "name": "Course name",
            "level": "Level",
            "duration": "Duration",
            "qualification_level": "Accreditation",
            "tuition": "Tuition per year",
            "intake": "Intakes",
            "scholarship": "Scholarship",
            "note": "Fee note",
            "display_order": "Position in the list",
        }
        help_texts = {
            "name": "e.g. Master in Artificial Intelligence, Data and Cloud.",
            "duration": "e.g. 1 year, 3 years.",
            "qualification_level": "e.g. Level 7 (RNCP41354), OTHM Level 5.",
            "tuition": "A number only, in the school's currency. Leave blank for on request.",
            "intake": "e.g. September / October & January.",
            "scholarship": "e.g. 25% scholarship: 7,500 EUR/yr + 690 EUR other expenses.",
            "note": "e.g. Total 18,000 EUR. 1st year 12,000 EUR + 690 EUR other expenses.",
            "display_order": "Lower numbers come first. Leave at 0 to sort by name.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On an existing course the school is already settled, so the
        # new-institution boxes only get in the way.
        if self.instance and self.instance.pk:
            self.fields["institution"].initial = self.instance.institution
            self.fields["institution"].required = True
            for name in (
                "new_country_name",
                "new_country_code",
                "new_country_currency",
                "new_country_is_european",
                "new_institution_name",
            ):
                self.fields[name].widget = forms.HiddenInput()

    def clean(self):
        data = super().clean()

        country = data.get("country")
        new_country = (data.get("new_country_name") or "").strip()
        institution = data.get("institution")
        new_institution = (data.get("new_institution_name") or "").strip()

        if institution is None and not new_institution:
            raise ValidationError(
                {"institution": "Choose a school, or type the name of a new one."}
            )

        # A new school needs somewhere to be. An existing one already knows.
        if institution is None:
            if country is None and not new_country:
                raise ValidationError(
                    {"country": "Choose a country for the new school, or add one."}
                )
            if country is None and new_country and not (data.get("new_country_code") or "").strip():
                raise ValidationError(
                    {"new_country_code": "A new country needs a two-letter code."}
                )
            if not (data.get("location") or "").strip():
                raise ValidationError(
                    {"location": "Say which city the new school is in."}
                )

        if institution and new_institution:
            raise ValidationError(
                {
                    "new_institution_name": (
                        "You picked an existing school and typed a new one. "
                        "Clear whichever you did not mean."
                    )
                }
            )

        if country and new_country:
            raise ValidationError(
                {
                    "new_country_name": (
                        "You picked an existing country and typed a new one. "
                        "Clear whichever you did not mean."
                    )
                }
            )

        # A course name has to be unique within its school, and the school may
        # not exist yet, so the model's own constraint cannot catch this.
        name = (data.get("name") or "").strip()
        if institution and name:
            clash = Program.objects.filter(institution=institution, name__iexact=name)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError(
                    {"name": f"{institution.name} already has a course with that name."}
                )

        return data

    def _resolve_country(self, data):
        if data.get("country"):
            return data["country"]

        name = data["new_country_name"].strip()
        existing = DestinationCountry.objects.filter(name__iexact=name).first()
        if existing:
            return existing

        return DestinationCountry.objects.create(
            name=name,
            code=data["new_country_code"].strip().upper(),
            currency=(data.get("new_country_currency") or "EUR").strip().upper(),
            is_european=data.get("new_country_is_european", False),
            display_order=DestinationCountry.objects.count(),
            is_active=True,
        )

    def _resolve_institution(self, data):
        institution = data.get("institution")

        if institution is None:
            country = self._resolve_country(data)
            name = data["new_institution_name"].strip()

            institution = Institution.objects.filter(name__iexact=name).first()
            if institution is None:
                slug = slugify(name)[:60] or "school"
                suffix = 1
                while Institution.objects.filter(slug=slug).exists():
                    suffix += 1
                    slug = f"{slugify(name)[:56]}-{suffix}"

                institution = Institution.objects.create(
                    slug=slug,
                    name=name,
                    country=country,
                    location=data.get("location", ""),
                    tagline=data.get("tagline", ""),
                    badge=data.get("badge") or "Partner School",
                    currency=(data.get("currency") or country.currency or "EUR").upper(),
                    application_fee=data.get("application_fee") or 0,
                    tuition_summary=data.get("tuition_summary", ""),
                    display_order=Institution.objects.filter(country=country).count(),
                    is_active=True,
                )
                return institution

        # An existing school is only changed where a value was actually typed,
        # so adding a course never quietly wipes a school's details.
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

        fee = data.get("application_fee")
        if fee is not None and fee != institution.application_fee:
            institution.application_fee = fee
            changed.append("application_fee")

        if changed:
            institution.save(update_fields=changed)

        return institution

    def save(self, commit=True):
        program = super().save(commit=False)
        program.institution = self._resolve_institution(self.cleaned_data)
        if commit:
            program.save()
        return program
