"""The course catalogue.

What staff change here is what the public site and the agent course browser
show, so the screens are built for editing in bulk: order and visibility are
editable straight from the list, and the filters match the ones agents use.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.utils.html import format_html

from config.admin_ui import muted, pill

from . import admin_import  # noqa: F401  (registers the Add Course screen)
from .forms import AddCourseForm
from .models import DestinationCountry, FaqItem, Institution, LandingReview, OriginCountry, Program


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
class InstitutionAdmin(admin.ModelAdmin):
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
        (None, {"fields": ("name", "slug", "country", "location", "cover_image", "tagline", "badge")}),
        (
            "Fees and tuition",
            {
                "fields": (
                    "currency",
                    ("application_fee_currency", "application_fee"),
                    "minimum_fee_ngn",
                    ("tuition_deposit_percent", "tuition_deposit_amount"),
                    "tuition_summary",
                ),
                "description": (
                    "Two currencies, on purpose. <b>Currency</b> is what this "
                    "school quotes its tuition and deposit in, and tuition is "
                    "never converted: it is shown to every applicant exactly as "
                    "the school states it. <b>Fee currency</b> is what the "
                    "application fee is quoted in, usually NGN, and that one is "
                    "converted into the applicant's own currency and charged in "
                    "Naira.<br><br>An application fee of 0 marks the school "
                    "fee-free: the applicant pays nothing and no registration "
                    "commission is earned on their file."
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
        """What this school charges, and what that is in Naira.

        The Naira figure is shown beside it because that is what the card is
        actually debited, and a fee quoted in another currency moves with the
        rate.
        """
        if obj.is_fee_free:
            return pill("Fee-free", "ok")
        own = f"{obj.fee_symbol}{obj.application_fee:,.2f}"
        if (obj.application_fee_currency or "").upper() == "NGN":
            return own
        return format_html(
            "{}<br>{}",
            own,
            muted(f"≈ ₦{obj.application_fee_ngn:,.0f}"),
        )

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
class ProgramAdmin(admin.ModelAdmin):
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
class DestinationCountryAdmin(admin.ModelAdmin):
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


class LandingReviewForm(forms.ModelForm):
    """Upload, blur, save: only the blurred picture is ever stored.

    ``source`` is the file the admin chooses. The blur tool reads it in the
    browser and empties the field before the form is sent, so the original
    never reaches the server; ``redacted`` carries the blurred picture instead.
    """

    source = forms.FileField(
        label="Image or PDF",
        required=False,
        help_text="A photo, screenshot or PDF (the first page is used).",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp,application/pdf"}),
    )
    redacted = forms.CharField(required=False, widget=forms.HiddenInput)
    blur_count = forms.IntegerField(required=False, widget=forms.HiddenInput)
    nothing_private = forms.BooleanField(
        label="This image has nothing private on it",
        required=False,
        help_text="Tick only for photos with no names, numbers or addresses on them.",
    )

    class Meta:
        model = LandingReview
        fields = ("kind", "title", "detail", "focus", "display_order", "is_active")

    def clean(self):
        from .landing_reviews import redacted_image

        data = super().clean()
        redacted = data.get("redacted")
        if not redacted:
            if not self.instance.pk:
                raise forms.ValidationError("Choose an image or PDF, blur anything private, then save.")
            return data
        if not (data.get("blur_count") or 0) and not data.get("nothing_private"):
            raise forms.ValidationError(
                "Drag boxes over every name, passport or ID number and address, "
                'or tick "This image has nothing private on it".'
            )
        try:
            data["redacted_file"] = redacted_image(redacted)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return data


@admin.register(LandingReview)
class LandingReviewAdmin(admin.ModelAdmin):
    form = LandingReviewForm
    change_form_template = "admin/catalog/landingreview/change_form.html"
    list_display = ("thumbnail", "title", "detail", "kind", "display_order", "is_active")
    list_display_links = ("thumbnail", "title")
    list_editable = ("display_order", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "detail")
    actions = ("action_show", "action_hide")
    fieldsets = (
        ("Image", {"fields": ("source", "nothing_private", "redacted", "blur_count")}),
        ("Card", {"fields": ("kind", "title", "detail", "focus")}),
        ("Landing page", {"fields": ("display_order", "is_active")}),
    )

    class Media:
        css = {"all": ("admin/landing_reviews/blur.css",)}
        js = ("admin/landing_reviews/blur.js",)

    @admin.display(description="Image")
    def thumbnail(self, obj):
        if not obj.image:
            return muted("None")
        return format_html(
            '<img src="{}" alt="" style="width:96px;height:64px;object-fit:cover;border-radius:6px;">', obj.image.url
        )

    def get_urls(self):
        from django.urls import path

        return [
            path(
                "pdf-preview/",
                self.admin_site.admin_view(self.pdf_preview),
                name="catalog_landingreview_pdf_preview",
            ),
            *super().get_urls(),
        ]

    def pdf_preview(self, request):
        """The first page of a PDF as a picture for the blur tool. Nothing is kept."""
        from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse

        from .landing_reviews import pdf_first_page

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            return JsonResponse({"error": "Not allowed."}, status=403)
        upload = request.FILES.get("file")
        if upload is None:
            return JsonResponse({"error": "Choose a PDF."}, status=400)
        try:
            picture = pdf_first_page(upload)
        except DjangoValidationError as exc:
            return JsonResponse({"error": " ".join(exc.messages)}, status=400)
        response = HttpResponse(picture, content_type="image/png")
        response["Cache-Control"] = "no-store"
        return response

    def save_model(self, request, obj, form, change):
        new_file = form.cleaned_data.get("redacted_file")
        old_name = obj.image.name if change and new_file else ""
        if new_file:
            obj.image.save(new_file.name, new_file, save=False)
        super().save_model(request, obj, form, change)
        if old_name and old_name != obj.image.name:
            obj.image.storage.delete(old_name)

    def delete_model(self, request, obj):
        name = obj.image.name
        super().delete_model(request, obj)
        if name:
            obj.image.storage.delete(name)

    def delete_queryset(self, request, queryset):
        names = [name for name in queryset.values_list("image", flat=True) if name]
        super().delete_queryset(request, queryset)
        for name in names:
            LandingReview._meta.get_field("image").storage.delete(name)

    @admin.action(description="Show on landing page")
    def action_show(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} shown on the landing page.", messages.SUCCESS)

    @admin.action(description="Hide from landing page")
    def action_hide(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} hidden from the landing page.", messages.SUCCESS)
