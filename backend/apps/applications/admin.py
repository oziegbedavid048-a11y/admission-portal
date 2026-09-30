"""The admissions desk.

Each screen has one job, and each action does one thing:

* **Applications**: read the file, verify its parts, and move it along the
  pipeline. Status fields are read-only here; they change only through the
  actions, so there is one way to do each thing.
* **Documents**: the one place to review uploads. Open a document, look at it,
  then Verify it or Reject it with a comment. The comment is emailed to the
  applicant (or their agent) and shown beside the document in their dashboard.
* **Letters**: the one place to issue and publish letters.
* **Correction requests**: approve or decline a requested change.
* **Visa Support Queue**: admitted students and anyone who sent their letter to
  the visa desk; start visa work, then confirm the visa.

Every action goes through ``services``, so the admin and the portals agree on
what a milestone does, and every change the applicant can see writes them a
notification.
"""

from django import forms
from django.contrib import admin, messages
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from config.admin_ui import button_link, muted, pill, plural

from . import services
from .models import (
    Application,
    CorrectionRequest,
    Document,
    Letter,
    Notification,
    Stage,
    VisaSupportApplication,
)

STATUS_TONE = {
    Application.Status.ADMITTED: "ok",
    Application.Status.REJECTED: "bad",
    Application.Status.IN_REVIEW: "wait",
}
VISA_TONE = {
    Application.VisaStatus.COMPLETED: "ok",
    Application.VisaStatus.IN_PROGRESS: "wait",
}
DOCUMENT_TONE = {"Verified": "ok", "Rejected": "bad"}


def verification_pill(obj):
    summary = obj.verification_summary
    status, cleared, total = summary["status"], summary["cleared_count"], summary["total_count"]
    if status == Application.VerificationStatus.VERIFIED:
        return pill("Verified", "ok")
    if status == Application.VerificationStatus.ACTION_REQUIRED:
        return pill("Needs action", "bad")
    if status == Application.VerificationStatus.IN_REVIEW:
        return pill(f"In review · {cleared}/{total}", "info")
    return pill(f"Not verified · {cleared}/{total}", "wait")


# ── Read-only lists shown on an application ─────────────────────────────


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    max_num = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class StageInline(ReadOnlyInline):
    """The five stages. They move with the pipeline actions, never by hand."""

    model = Stage
    fields = ("order", "name", "status", "eta")
    readonly_fields = fields
    ordering = ("order",)


class DocumentInline(ReadOnlyInline):
    """Uploads on this file. Reviewing happens on the Documents screen."""

    model = Document
    fields = ("name", "status_label", "review_link", "uploaded_at")
    readonly_fields = fields
    ordering = ("uploaded_at",)
    verbose_name_plural = "Documents (review them on the Documents screen)"

    @admin.display(description="Status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), DOCUMENT_TONE.get(obj.status, "wait"))

    @admin.display(description="")
    def review_link(self, obj):
        return button_link(reverse("admin:applications_document_change", args=[obj.pk]), "Review")


class LetterInline(ReadOnlyInline):
    """Letters on this file. Issuing happens on the Letters screen."""

    model = Letter
    fk_name = "application"
    fields = ("title", "kind", "is_published", "issued_at", "open_link")
    readonly_fields = fields
    verbose_name_plural = "Letters (issue them on the Letters screen)"

    @admin.display(description="")
    def open_link(self, obj):
        return button_link(reverse("admin:applications_letter_change", args=[obj.pk]), "Open")


class CorrectionInline(ReadOnlyInline):
    """Requested changes. Approve or decline them on the Correction requests screen."""

    model = CorrectionRequest
    fields = ("ticket", "field", "corrected_value", "status", "open_link")
    readonly_fields = fields
    ordering = ("-created_at",)
    verbose_name_plural = "Correction requests (decide them on the Correction requests screen)"

    @admin.display(description="")
    def open_link(self, obj):
        return button_link(reverse("admin:applications_correctionrequest_change", args=[obj.pk]), "Open")


class NotificationInline(ReadOnlyInline):
    """What the applicant has been told, newest first."""

    model = Notification
    fields = ("text", "is_read", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


# ── Filters ─────────────────────────────────────────────────────────────


class DocumentsToReviewFilter(admin.SimpleListFilter):
    title = "documents"
    parameter_name = "documents"

    def lookups(self, request, model_admin):
        return (("to_review", "Waiting for review"), ("rejected", "Has a rejected document"))

    def queryset(self, request, queryset):
        if self.value() == "to_review":
            return queryset.filter(documents__status=Document.Status.PENDING).distinct()
        if self.value() == "rejected":
            return queryset.filter(documents__status=Document.Status.REJECTED).distinct()
        return queryset


class FiledByFilter(admin.SimpleListFilter):
    title = "filed by"
    parameter_name = "filed_by"

    def lookups(self, request, model_admin):
        return (("agent", "Partner agent"), ("applicant", "Applicant"))

    def queryset(self, request, queryset):
        if self.value() == "agent":
            return queryset.filter(submitted_by_agent__isnull=False)
        if self.value() == "applicant":
            return queryset.filter(submitted_by_agent__isnull=True)
        return queryset


class PlainSelectsMixin:
    """Drop the add / edit / delete / view icons beside dropdowns.

    Countries, schools and courses are managed on their own screens, so a
    dropdown here only picks one.
    """

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        widget = getattr(field, "widget", None)
        for flag in ("can_add_related", "can_change_related", "can_delete_related", "can_view_related"):
            if hasattr(widget, flag):
                setattr(widget, flag, False)
        return field


# ── Applications ────────────────────────────────────────────────────────


@admin.register(Application)
class ApplicationAdmin(PlainSelectsMixin, admin.ModelAdmin):
    list_display = (
        "reference",
        "full_name",
        "university",
        "verification",
        "documents_state",
        "stage",
        "status_label",
        "submitted_at",
    )
    list_filter = (
        "status",
        "verification_status",
        DocumentsToReviewFilter,
        "destination_country",
        FiledByFilter,
    )
    search_fields = ("reference", "full_name", "email", "institution__name", "custom_course_name")
    autocomplete_fields = ("institution", "applicant")
    filter_horizontal = ("programs",)
    date_hierarchy = "submitted_at"
    list_per_page = 40
    inlines = (DocumentInline, LetterInline, CorrectionInline, StageInline, NotificationInline)

    readonly_fields = (
        "reference",
        "applicant",
        "submitted_by_agent",
        "status",
        "visa_status",
        "verification_status",
        "personal_details_verified",
        "academic_details_verified",
        "documents_verified",
        "payment_verified",
        "verified_at",
        "verified_by",
        "transferred_to_visa_support",
        "payment_summary",
        "course_request",
        "submitted_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Where the file stands",
            {
                "description": "Change these with the actions on the Applications list.",
                "fields": (
                    ("reference", "status", "visa_status"),
                    ("verification_status", "verified_at", "verified_by"),
                    ("personal_details_verified", "academic_details_verified", "documents_verified", "payment_verified"),
                    ("transferred_to_visa_support", "payment_summary"),
                ),
            },
        ),
        ("Applicant", {"fields": (("full_name", "email"), ("phone", "address"), ("origin_country", "destination_country"), ("applicant", "submitted_by_agent"))}),
        ("Education", {"fields": ("previous_schools", ("qualification", "year_graduated", "grade_gpa"))}),
        ("University and course", {"fields": ("course_request", "institution", "programs")}),
        ("Internal notes", {"fields": ("verification_notes", "notes", ("submitted_at", "updated_at"))}),
    )

    actions = (
        "action_verify_personal",
        "action_verify_academic",
        "action_verify_payment",
        "action_flag_action_required",
        "action_reset_verification",
        "action_send_to_institution",
        "action_mark_admitted",
        "action_mark_rejected",
        "action_send_email_to_applicants",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("institution", "destination_country", "submitted_by_agent", "payment")
            .prefetch_related("stages")
            .annotate(
                pending_docs=Count("documents", filter=Q(documents__status=Document.Status.PENDING), distinct=True),
                rejected_docs=Count("documents", filter=Q(documents__status=Document.Status.REJECTED), distinct=True),
                total_docs=Count("documents", distinct=True),
            )
        )

    # ── Columns ──

    @admin.display(description="University", ordering="institution__name")
    def university(self, obj):
        if obj.is_custom_course:
            return pill("Course request", "info")
        return obj.institution.name if obj.institution else muted("Not chosen")

    @admin.display(description="Verification", ordering="verification_status")
    def verification(self, obj):
        return verification_pill(obj)

    @admin.display(description="Documents")
    def documents_state(self, obj):
        if not obj.total_docs:
            return muted("None")
        if obj.rejected_docs:
            return pill(f"{obj.rejected_docs} rejected", "bad")
        if obj.pending_docs:
            return pill(f"{obj.pending_docs} to review", "wait")
        return pill("All verified", "ok")

    @admin.display(description="Stage")
    def stage(self, obj):
        current = obj.current_stage
        if current is None:
            return muted("None")
        return format_html("{} {}", current.name, muted(f"· {obj.current_stage_index + 1} of {len(obj.stages.all())}"))

    @admin.display(description="Status", ordering="status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), STATUS_TONE.get(obj.status, "idle"))

    @admin.display(description="Payment")
    def payment_summary(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return muted("No payment yet")
        return format_html(
            '{} · {} · <a href="{}">{}</a>',
            payment.display_total,
            payment.get_status_display(),
            reverse("admin:payments_payment_change", args=[payment.pk]),
            payment.reference,
        )

    @admin.display(description="Course request")
    def course_request(self, obj):
        if not obj.is_custom_course:
            return muted("Chose a course from the catalogue")
        return format_html(
            '<div class="gs-callout gs-callout--info"><strong>{}</strong> in {}<br>'
            'Contact the applicant to match a university: <a href="mailto:{}">{}</a> · {}</div>',
            obj.custom_course_name or "Course not named",
            obj.destination_country.name if obj.destination_country else "any country",
            obj.email,
            obj.email,
            obj.phone or "no phone",
        )

    # ── Actions: one job each, in the order a file is worked ──

    def _run(self, request, queryset, step, done, skipped_reason, level=messages.SUCCESS):
        changed = [application for application in queryset if step(application)]
        skipped = queryset.count() - len(changed)
        if changed:
            self.message_user(request, f"{plural(len(changed), 'application')} {done}.", level)
        if skipped:
            self.message_user(request, f"{plural(skipped, 'application')} skipped: {skipped_reason}.", messages.INFO)

    def _verify(self, request, queryset, checkpoint, done):
        self._run(
            request,
            queryset,
            lambda a: services.verify_checkpoint(a, checkpoint, verified_by=request.user),
            done,
            "already verified",
        )

    @admin.action(description="Verify personal details")
    def action_verify_personal(self, request, queryset):
        self._verify(request, queryset, "personal", "had personal details verified")

    @admin.action(description="Verify academic details")
    def action_verify_academic(self, request, queryset):
        self._verify(request, queryset, "academic", "had academic details verified")

    @admin.action(description="Verify application fee")
    def action_verify_payment(self, request, queryset):
        self._verify(request, queryset, "payment", "had the application fee verified")

    @admin.action(description="Flag: needs action from the applicant")
    def action_flag_action_required(self, request, queryset):
        self._run(
            request, queryset,
            lambda a: services.flag_action_required(a, verified_by=request.user),
            "flagged as needing action", "already flagged", messages.WARNING,
        )

    @admin.action(description="Reset verification")
    def action_reset_verification(self, request, queryset):
        self._run(request, queryset, services.reset_verification, "reset to not verified", "nothing to reset", messages.WARNING)

    @admin.action(description="Send to university")
    def action_send_to_institution(self, request, queryset):
        self._run(
            request, queryset, services.send_to_institution, "sent to the university",
            "documents not all verified yet, or the file is already with the university or decided",
        )

    @admin.action(description="Grant admission")
    def action_mark_admitted(self, request, queryset):
        self._run(request, queryset, services.mark_admitted, "admitted", "already admitted")

    @admin.action(description="Decline application")
    def action_mark_rejected(self, request, queryset):
        self._run(request, queryset, services.mark_rejected, "declined", "already declined", messages.WARNING)

    @admin.action(description="Email a message")
    def action_send_email_to_applicants(self, request, queryset):
        """Write to the owner of each file: the applicant, or the agent who filed it."""
        if request.POST.get("apply") == "send_email":
            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(request, "Subject and message are both required.", messages.ERROR)
                return None
            for application in queryset:
                services.send_applicant_email_message(application, subject, message_body)
            self.message_user(
                request,
                f"Message sent for {plural(queryset.count(), 'application')}. Files filed by an "
                "agent were written to the agent, not the student.",
                messages.SUCCESS,
            )
            return None
        return render(request, "admin/send_email_intermediate.html", {"title": "Email a message", "applicants": queryset})


# ── Documents: the one place to review uploads ──────────────────────────


class RejectDocumentForm(forms.Form):
    note = forms.CharField(
        label="What is wrong, and what should they upload instead?",
        widget=forms.Textarea(attrs={"rows": 5, "cols": 70}),
        max_length=2000,
        help_text="This is emailed to the applicant word for word and shown beside the document in their dashboard.",
    )


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Open a document, look at it, then Verify it or Reject it with a comment."""

    list_display = ("name", "applicant", "status_label", "uploaded_at", "open_link")
    list_filter = ("status", "kind", "uploaded_at")
    search_fields = ("name", "original_filename", "application__reference", "application__full_name")
    date_hierarchy = "uploaded_at"
    list_select_related = ("application",)
    actions = ("action_verify",)
    change_form_template = "admin/applications/document/review.html"

    readonly_fields = (
        "application_link", "name", "kind", "original_filename", "size", "status_label",
        "review_note", "reviewed_at", "reviewed_by", "uploaded_at",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        # Waiting for review first, then the rest.
        waiting_first = Case(When(status=Document.Status.PENDING, then=0), default=1, output_field=IntegerField())
        return super().get_queryset(request).order_by(waiting_first, "-uploaded_at")

    @admin.display(description="Applicant", ordering="application__full_name")
    def applicant(self, obj):
        return f"{obj.application.full_name} · {obj.application.reference}"

    @admin.display(description="Application")
    def application_link(self, obj):
        return format_html(
            '<a href="{}">{} · {}</a>',
            reverse("admin:applications_application_change", args=[obj.application_id]),
            obj.application.full_name,
            obj.application.reference,
        )

    @admin.display(description="Status", ordering="status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), DOCUMENT_TONE.get(obj.status, "wait"))

    @admin.display(description="Size")
    def size(self, obj):
        return obj.human_size

    @admin.display(description="")
    def open_link(self, obj):
        return button_link(reverse("admin:applications_document_change", args=[obj.pk]), "Review")

    # One page per decision.
    def get_urls(self):
        return [
            path("<int:pk>/verify/", self.admin_site.admin_view(self.verify_view), name="applications_document_verify"),
            path("<int:pk>/reject/", self.admin_site.admin_view(self.reject_view), name="applications_document_reject"),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        document = get_object_or_404(Document, pk=object_id)
        url = document.file.url if document.file else ""
        name = (document.original_filename or document.file.name if document.file else "").lower()
        extra_context = {
            **(extra_context or {}),
            "title": "Review document",
            "doc": document,
            "file_url": url,
            "is_pdf": name.endswith(".pdf"),
            "is_image": name.endswith((".jpg", ".jpeg", ".png", ".webp")),
            "verify_url": reverse("admin:applications_document_verify", args=[document.pk]),
            "reject_url": reverse("admin:applications_document_reject", args=[document.pk]),
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def verify_view(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if request.method == "POST":
            services.verify_documents([document], reviewed_by=request.user)
            self.message_user(request, f"{document.name} verified. The applicant has been told.", messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:applications_document_changelist"))

    def reject_view(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        form = RejectDocumentForm(request.POST or None, initial={"note": document.review_note})
        if request.method == "POST" and form.is_valid():
            services.reject_document(document, form.cleaned_data["note"], reviewed_by=request.user)
            self.message_user(
                request,
                f"{document.name} rejected. Your comment was emailed and is shown in their dashboard.",
                messages.WARNING,
            )
            return HttpResponseRedirect(reverse("admin:applications_document_changelist"))
        return render(
            request,
            "admin/applications/document/reject.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Reject {document.name}",
                "doc": document,
                "form": form,
                "opts": self.model._meta,
                "back_url": reverse("admin:applications_document_change", args=[document.pk]),
            },
        )

    @admin.action(description="Verify selected documents")
    def action_verify(self, request, queryset):
        count = services.verify_documents(list(queryset.select_related("application")), reviewed_by=request.user)
        skipped = queryset.count() - count
        if count:
            self.message_user(request, f"{plural(count, 'document')} verified.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"{plural(skipped, 'document')} skipped: already verified.", messages.INFO)


# ── Letters: the one place to issue letters ─────────────────────────────


@admin.register(Letter)
class LetterAdmin(PlainSelectsMixin, admin.ModelAdmin):
    """Issue a letter: upload it, then publish it to the applicant's dashboard."""

    list_display = ("title", "application", "kind", "published", "issued_at")
    list_filter = ("kind", "is_published", "issued_at")
    search_fields = ("title", "application__reference", "application__full_name")
    autocomplete_fields = ("application",)
    date_hierarchy = "issued_at"
    readonly_fields = ("is_published", "issued_by", "created_at", "download")
    actions = ("action_publish", "action_unpublish")
    fieldsets = (
        ("Letter", {"fields": ("application", "kind", "title", "file", "download", "note")}),
        ("Publication", {
            "description": "Save the letter, then use Publish on the Letters list to show it to the applicant.",
            "fields": ("is_published", "issued_at", "issued_by", "created_at"),
        }),
    )

    @admin.display(description="Published", boolean=True, ordering="is_published")
    def published(self, obj):
        return obj.is_published

    @admin.display(description="File")
    def download(self, obj):
        if not obj.file:
            return muted("None")
        return button_link(obj.file.url, "Open letter", new_tab=True)

    def save_model(self, request, obj, form, change):
        if obj.issued_by_id is None:
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish to the applicant")
    def action_publish(self, request, queryset):
        from django.utils import timezone

        count = 0
        for letter in queryset.filter(is_published=False):
            letter.is_published = True
            letter.issued_at = letter.issued_at or timezone.now()
            letter.save(update_fields=["is_published", "issued_at"])
            services.announce_letter(letter)
            count += 1
        self.message_user(request, f"{plural(count, 'letter')} published and emailed.", messages.SUCCESS)

    @admin.action(description="Unpublish (hide from the applicant)")
    def action_unpublish(self, request, queryset):
        count = queryset.filter(is_published=True).update(is_published=False)
        self.message_user(request, f"{plural(count, 'letter')} hidden.", messages.WARNING)


# ── Correction requests ─────────────────────────────────────────────────


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    """Approve a requested change (written to the file where possible) or decline it."""

    list_display = ("ticket", "application", "field", "current_value", "corrected_value", "status_label", "created_at")
    list_filter = ("status", "field", "created_at")
    search_fields = ("ticket", "application__reference", "application__full_name", "corrected_value")
    date_hierarchy = "created_at"
    readonly_fields = ("ticket", "application", "field", "status", "current_value", "corrected_value", "reason", "evidence_link", "created_at")
    fields = readonly_fields
    actions = ("action_approve", "action_decline")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Status", ordering="status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), {"verified": "ok", "declined": "bad"}.get(obj.status, "wait"))

    @admin.display(description="Evidence")
    def evidence_link(self, obj):
        if not obj.evidence:
            return muted("None attached")
        return button_link(obj.evidence.url, "Open evidence", new_tab=True)

    @admin.action(description="Approve correction")
    def action_approve(self, request, queryset):
        approved = applied = 0
        for correction in queryset:
            changed, written = services.approve_correction(correction)
            approved += int(changed)
            applied += int(written)
        self.message_user(
            request,
            f"{plural(approved, 'correction')} approved, {applied} written to the file."
            + (" The rest need changing on the application itself." if approved > applied else ""),
            messages.SUCCESS if approved else messages.INFO,
        )

    @admin.action(description="Decline correction")
    def action_decline(self, request, queryset):
        count = sum(1 for correction in queryset if services.decline_correction(correction))
        self.message_user(request, f"{plural(count, 'correction')} declined.", messages.WARNING)


# ── Visa Support Queue ──────────────────────────────────────────────────


@admin.register(VisaSupportApplication)
class VisaSupportApplicationAdmin(admin.ModelAdmin):
    """Admitted students, and anyone who sent their letter to the visa desk."""

    list_display = ("reference", "full_name", "institution", "visa_label", "sent_by_applicant", "letters")
    list_filter = ("visa_status", "transferred_to_visa_support", "destination_country")
    search_fields = ("reference", "full_name", "email", "phone", "institution__name")
    date_hierarchy = "submitted_at"
    list_per_page = 40
    inlines = (LetterInline, NotificationInline)
    readonly_fields = (
        "reference", "status", "visa_status", "transferred_to_visa_support", "transferred_to_visa_support_at",
        "full_name", "email", "phone", "destination_country", "institution", "course_names", "letters",
    )
    fieldsets = (
        ("Visa", {"fields": (("reference", "status", "visa_status"), ("transferred_to_visa_support", "transferred_to_visa_support_at"))}),
        ("Student", {"fields": (("full_name", "email", "phone"), ("destination_country", "institution"), "course_names")}),
        ("Letters", {"fields": ("letters",)}),
    )
    actions = ("action_start_visa_processing", "action_mark_visa_verified")

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(Q(status=Application.Status.ADMITTED) | Q(transferred_to_visa_support=True))
            .select_related("institution", "destination_country")
            .prefetch_related("letters", "programs")
        )

    @admin.display(description="Visa", ordering="visa_status")
    def visa_label(self, obj):
        return pill(obj.get_visa_status_display(), VISA_TONE.get(obj.visa_status, "idle"))

    @admin.display(description="Sent by applicant", boolean=True, ordering="transferred_to_visa_support")
    def sent_by_applicant(self, obj):
        return obj.transferred_to_visa_support

    @admin.display(description="Course")
    def course_names(self, obj):
        return ", ".join(program.name for program in obj.programs.all()) or obj.custom_course_name or "—"

    @admin.display(description="Letters")
    def letters(self, obj):
        items = [letter for letter in obj.letters.all() if letter.file]
        if not items:
            return muted("No letters yet")
        return format_html_join(" ", "{}", ((button_link(letter.file.url, letter.title, new_tab=True),) for letter in items))

    @admin.action(description="Start visa processing")
    def action_start_visa_processing(self, request, queryset):
        changed = sum(1 for application in queryset if services.start_visa_processing(application))
        skipped = queryset.count() - changed
        if changed:
            self.message_user(request, f"{plural(changed, 'application')} now in visa processing.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"{plural(skipped, 'application')} skipped: not admitted, or visa work already started.", messages.INFO)

    @admin.action(description="Confirm visa approved (credits the agent's visa commission)")
    def action_mark_visa_verified(self, request, queryset):
        moved = paid = 0
        for application in queryset:
            changed, amount = services.mark_visa_verified(application)
            moved += int(changed)
            paid += amount
        skipped = queryset.count() - moved
        if moved:
            self.message_user(
                request,
                f"{plural(moved, 'visa')} confirmed." + (f" ₦{paid:,.0f} commission credited to partner agents." if paid else ""),
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(request, f"{plural(skipped, 'application')} skipped: not admitted, or visa already confirmed.", messages.INFO)
