"""Add Course: paste a school's list, check it, save it.

This replaces three separate screens. Countries, schools and courses used to be
added one at a time and in the right order, which is both slow and the reason
half-finished schools ended up in the catalogue. Here the whole list arrives in
one paste, the parser works out what each column is, and nothing is written
until the admissions desk has seen every row and confirmed it.

The screen has two stages held in one view. Stage one is the paste box. Stage
two shows what was read, as editable fields, above the school and fee details.
The pasted text is carried through in a hidden field rather than kept in the
session, so two people can work on different imports at once and a half-finished
import never outlives the tab it is in.
"""

from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from .import_forms import (
    CourseRowFormSet,
    DestinationForm,
    PasteForm,
    summarise_tuition,
)
from .importer import parse_paste
from .models import CourseImport, DestinationCountry, Program


def _initial_from_parse(parsed):
    """Turn a parse into the two sets of initial data stage two needs."""
    country = DestinationCountry.objects.filter(name__iexact=parsed.country).first()

    details = {
        "country": country.pk if country else None,
        "new_country_name": "" if country else parsed.country,
        "new_country_currency": parsed.currency or "EUR",
        "new_country_is_european": True,
        "location": parsed.location,
        "tagline": parsed.tagline,
        "badge": parsed.badge,
        "currency": parsed.currency or (country.currency if country else "EUR"),
        "tuition_summary": parsed.tuition_summary,
        "application_fee": parsed.application_fee if parsed.application_fee is not None else 0,
    }

    from .models import Institution

    school = None
    if parsed.school:
        school = Institution.objects.filter(name__iexact=parsed.school).first()
    if school:
        details["institution"] = school.pk
        details["currency"] = details["currency"] or school.currency
        details["application_fee"] = (
            parsed.application_fee if parsed.application_fee is not None else school.application_fee
        )
    else:
        details["new_institution_name"] = parsed.school

    rows = [{"include": True, **course.as_dict()} for course in parsed.courses]
    return details, rows


@admin.register(CourseImport)
class CourseImportAdmin(admin.ModelAdmin):
    """One screen. Its list view is the importer; there is nothing to list."""

    def has_add_permission(self, request):
        # Adding happens through the paste, not through a blank change form.
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def changelist_view(self, request, extra_context=None):
        context = {
            **self.admin_site.each_context(request),
            "title": "Add course",
            "opts": self.model._meta,
            "program_changelist": reverse("admin:catalog_program_changelist"),
            "institution_changelist": reverse("admin:catalog_institution_changelist"),
            "country_changelist": reverse("admin:catalog_destinationcountry_changelist"),
            # The FAQ and the exchange rates are off the index too, so this is
            # the only place they are linked from.
            "faq_changelist": reverse("admin:catalog_faqitem_changelist"),
            "rates_changelist": reverse("admin:catalog_origincountry_changelist"),
        }

        stage = request.POST.get("stage") if request.method == "POST" else None

        if request.method == "POST" and request.POST.get("back"):
            context["paste_form"] = PasteForm(initial={"paste": request.POST.get("paste", "")})
            context["stage"] = "paste"
            return render(request, "admin/catalog/add_course.html", context)
        if stage == "preview":
            return self._save_stage(request, context)
        if stage == "paste":
            return self._preview_stage(request, context)

        context["paste_form"] = PasteForm()
        context["stage"] = "paste"
        return render(request, "admin/catalog/add_course.html", context)

    # ── Stage one to two ─────────────────────────────────────────────

    def _preview_stage(self, request, context):
        paste_form = PasteForm(request.POST)
        if not paste_form.is_valid():
            context["paste_form"] = paste_form
            context["stage"] = "paste"
            return render(request, "admin/catalog/add_course.html", context)

        text = paste_form.cleaned_data["paste"]
        parsed = parse_paste(
            text, known_countries=DestinationCountry.objects.values_list("name", flat=True)
        )

        if not parsed.courses:
            for warning in parsed.warnings:
                self.message_user(request, warning, messages.ERROR)
            context["paste_form"] = paste_form
            context["stage"] = "paste"
            return render(request, "admin/catalog/add_course.html", context)

        details, rows = _initial_from_parse(parsed)
        context.update(
            stage="preview",
            paste=text,
            details_form=DestinationForm(initial=details),
            formset=CourseRowFormSet(initial=rows),
            warnings=parsed.warnings,
        )
        return render(request, "admin/catalog/add_course.html", context)

    # ── Stage two to saved ───────────────────────────────────────────

    def _save_stage(self, request, context):
        details_form = DestinationForm(request.POST)
        formset = CourseRowFormSet(request.POST)
        paste = request.POST.get("paste", "")

        if not (details_form.is_valid() and formset.is_valid()):
            context.update(
                stage="preview",
                paste=paste,
                details_form=details_form,
                formset=formset,
                warnings=[],
            )
            return render(request, "admin/catalog/add_course.html", context)

        rows = [form.cleaned_data for form in formset if form.cleaned_data.get("include")]
        if not rows:
            self.message_user(request, "No rows were ticked, so nothing was saved.", messages.WARNING)
            context.update(
                stage="preview",
                paste=paste,
                details_form=details_form,
                formset=formset,
                warnings=[],
            )
            return render(request, "admin/catalog/add_course.html", context)

        created, skipped, country_created, school_created, school = self._write(details_form, rows)

        parts = []
        if country_created:
            parts.append(f"added {school.country.name}")
        if school_created:
            parts.append(f"added {school.name}")
        parts.append(f"{created} course{'' if created == 1 else 's'} saved to {school.name}")
        if skipped:
            parts.append(
                f"{skipped} skipped because {school.name} already had a course with that name"
            )

        self.message_user(request, ", ".join(parts).capitalize() + ".", messages.SUCCESS)
        return redirect(reverse("admin:catalog_courseimport_changelist"))

    @transaction.atomic
    def _write(self, details_form, rows):
        school, school_created, country_created = details_form.resolve_institution()

        if not school.tuition_summary:
            summary = summarise_tuition(rows, school.currency)
            if summary:
                school.tuition_summary = summary
                school.save(update_fields=["tuition_summary"])

        existing = {name.lower() for name in school.programs.values_list("name", flat=True)}
        order = school.programs.count()

        created = 0
        skipped = 0
        for row in rows:
            name = row["name"].strip()
            if name.lower() in existing:
                skipped += 1
                continue
            Program.objects.create(
                institution=school,
                name=name,
                level=row.get("level") or Program.Level.OTHER,
                duration=row.get("duration", ""),
                qualification_level=row.get("qualification_level", ""),
                tuition=row.get("tuition"),
                intake=row.get("intake", ""),
                scholarship=row.get("scholarship", ""),
                note=row.get("note", ""),
                display_order=order,
            )
            existing.add(name.lower())
            order += 1
            created += 1

        return created, skipped, country_created, school_created, school
