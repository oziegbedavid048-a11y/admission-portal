"""The course catalogue.

What staff change here is what the public site and the agent course browser
show, so the screens are built for editing in bulk: order and visibility are
editable straight from the list, and the filters match the ones agents use.
"""

from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from . import admin_import  # noqa: F401  (registers the Add Course screen)
from .forms import AddCourseForm
from .models import DestinationCountry, FaqItem, Institution, OriginCountry, Program


class HiddenFromIndex:
    """Keeps a screen working while taking it off the admin index.

    Everything in the catalogue is added through Add Course, so listing the
    schools, the countries and the courses beside it as three more entries is
    what made this section hard to read. The screens themselves still matter for
    correcting or removing a row later, so they keep their URLs and Add Course
    links to them; they simply are not sections of their own.
    """

    def get_model_perms(self, request):
        return {}


class ProgramInline(admin.TabularInline):
    """Edit an institution's courses without leaving the institution."""

    model = Program
    extra = 1
    fields = ("display_order", "name", "level", "duration", "tuition", "intake")
    ordering = ("display_order", "name")


@admin.register(Institution)
class InstitutionAdmin(HiddenFromIndex, admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "location",
        "course_count",
        "fee",
        "display_order",
        "is_active",
    )
    list_display_links = ("name",)
    # Reordering and switching an institution on or off is the common edit, so
    # both are done from the list rather than one change page at a time.
    list_editable = ("display_order", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name", "location", "tagline")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProgramInline,)
    actions = ("action_activate", "action_deactivate")
    save_on_top = True

    fieldsets = (
        (None, {"fields": ("name", "slug", "country", "location", "tagline", "badge")}),
        (
            "Fees and tuition",
            {
                "fields": ("currency", "application_fee", "tuition_summary"),
                "description": (
                    "An application fee of 0 marks the institution fee-free. The "
                    "applicant then pays nothing, and no registration commission "
                    "is earned on their file."
                ),
            },
        ),
        ("Listing", {"fields": ("features", "display_order", "is_active")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("country")
            .annotate(programs_total=Count("programs"))
        )

    @admin.display(description="Courses", ordering="programs_total")
    def course_count(self, obj):
        return obj.programs_total

    @admin.display(description="Application fee", ordering="application_fee")
    def fee(self, obj):
        if obj.is_fee_free:
            return format_html(
                '<span style="background:#dcfce7;color:#166534;border-radius:999px;'
                'padding:2px 9px;font-size:11px;font-weight:700">Fee-free</span>'
            )
        return f"{obj.currency} {obj.application_fee:,.2f}"

    @admin.action(description="Show on the site")
    def action_activate(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} institution(s) now listed.", messages.SUCCESS)

    @admin.action(description="Hide from the site")
    def action_deactivate(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{count} institution(s) hidden. Existing applications are unaffected.",
            messages.WARNING,
        )


@admin.register(Program)
class ProgramAdmin(HiddenFromIndex, admin.ModelAdmin):
    """Every course on the platform, for correcting one after the fact.

    New courses arrive through Add Course, which reads a whole pasted list at
    once. This screen is what is left for the single edits that follow: fixing a
    tuition figure, renaming a course, taking one off the site. It can still
    create a course, and its school and country with it, but nothing routes here
    to do that.
    """

    form = AddCourseForm
    list_display = ("name", "institution", "country", "level", "duration", "fee", "intake", "display_order")
    list_display_links = ("name",)
    list_editable = ("display_order",)
    list_filter = ("institution__country", "level", "institution")
    search_fields = ("name", "institution__name", "qualification_level", "intake")
    list_per_page = 50
    save_on_top = True
    actions = ("action_set_bachelors", "action_set_masters", "action_set_phd", "action_set_diploma")

    add_fieldsets = (
        (
            "Where is it taught",
            {
                "fields": (
                    "country",
                    ("new_country_name", "new_country_code"),
                    ("new_country_currency", "new_country_is_european"),
                ),
                "description": (
                    "Pick the country. If it is not listed yet, leave the picker "
                    "empty and fill in the new-country boxes instead."
                ),
            },
        ),
        (
            "Which school",
            {
                "fields": (
                    "institution",
                    "new_institution_name",
                    "location",
                    "tagline",
                    ("badge", "currency"),
                    ("application_fee", "tuition_summary"),
                ),
                "description": (
                    "Pick a school, or name a new one. On an existing school, "
                    "anything you type here updates it; anything you leave blank "
                    "is kept as it is."
                ),
            },
        ),
        (
            "The course",
            {
                "fields": (
                    "name",
                    ("level", "duration"),
                    "qualification_level",
                    "intake",
                    "display_order",
                )
            },
        ),
        ("Money", {"fields": ("tuition", "scholarship", "note")}),
    )

    edit_fieldsets = (
        ("Where", {"fields": ("institution",)}),
        (
            "The course",
            {
                "fields": (
                    "name",
                    ("level", "duration"),
                    "qualification_level",
                    "intake",
                    "display_order",
                )
            },
        ),
        ("Money", {"fields": ("tuition", "scholarship", "note")}),
        (
            "The school's own details",
            {
                "fields": (
                    "location",
                    "tagline",
                    ("badge", "currency"),
                    ("application_fee", "tuition_summary"),
                ),
                "classes": ("collapse",),
                "description": (
                    "These belong to the school, not this course, so a change "
                    "here shows on every course it teaches."
                ),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        return self.edit_fieldsets if obj else self.add_fieldsets

    def get_changeform_initial_data(self, request):
        """Prefill the school's details so an edit shows what is on file."""
        return {"application_fee": 0, "currency": "EUR"}

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is not None:
            institution = obj.institution
            for field, value in (
                ("location", institution.location),
                ("tagline", institution.tagline),
                ("badge", institution.badge),
                ("currency", institution.currency),
                ("application_fee", institution.application_fee),
                ("tuition_summary", institution.tuition_summary),
            ):
                form.base_fields[field].initial = value
        return form

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("institution", "institution__country")

    @admin.display(description="Country", ordering="institution__country__name")
    def country(self, obj):
        return obj.institution.country.name

    @admin.display(description="Tuition", ordering="tuition")
    def fee(self, obj):
        if obj.tuition is None:
            return "On request"
        return f"{obj.institution.currency} {obj.tuition:,.0f}"

    def _set_level(self, request, queryset, level):
        count = queryset.update(level=level)
        self.message_user(
            request,
            f"{count} course(s) moved to {dict(Program.Level.choices)[level]}.",
            messages.SUCCESS,
        )

    @admin.action(description="Set level: Bachelor's")
    def action_set_bachelors(self, request, queryset):
        self._set_level(request, queryset, Program.Level.BACHELORS)

    @admin.action(description="Set level: Masters & MBA")
    def action_set_masters(self, request, queryset):
        self._set_level(request, queryset, Program.Level.MASTERS)

    @admin.action(description="Set level: PhD & doctoral")
    def action_set_phd(self, request, queryset):
        self._set_level(request, queryset, Program.Level.PHD)

    @admin.action(description="Set level: Diplomas & certificates")
    def action_set_diploma(self, request, queryset):
        self._set_level(request, queryset, Program.Level.DIPLOMAS)



@admin.register(OriginCountry)
class OriginCountryAdmin(HiddenFromIndex, admin.ModelAdmin):
    list_display = ("name", "currency", "symbol", "ngn_per_unit")
    list_editable = ("ngn_per_unit",)
    search_fields = ("name", "currency")


@admin.register(DestinationCountry)
class DestinationCountryAdmin(HiddenFromIndex, admin.ModelAdmin):
    list_display = ("name", "code", "currency", "institutions_count", "is_european", "display_order", "is_active")
    list_display_links = ("name",)
    list_editable = ("display_order", "is_active")
    search_fields = ("name", "code")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total=Count("institutions"))

    @admin.display(description="Institutions", ordering="total")
    def institutions_count(self, obj):
        return obj.total


@admin.register(FaqItem)
class FaqItemAdmin(HiddenFromIndex, admin.ModelAdmin):
    list_display = ("question", "display_order", "is_active")
    list_display_links = ("question",)
    list_editable = ("display_order", "is_active")
    search_fields = ("question", "answer")
