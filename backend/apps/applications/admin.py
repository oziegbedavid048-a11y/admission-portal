"""The admissions desk.

Each screen has one job, and each action does one thing:

* **Applications**: files applicants made themselves. Read the file, verify
  its parts, and move it along the pipeline.
* **Agent applications**: every partner agent; open one to see the students
  that agent registered, with a download of everything on each file.
  Status fields on both screens are read-only; they change only through the
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

from apps.accounts.models import User
from apps.accounts.deletion import AccountDeleteMixin
from apps.accounts.testdata import RealDataOnlyAdmin
from config.admin_ui import button_link, muted, pill, plural

from . import services
from .models import (
    AgentApplication,
    AgentApplications,
    AgentDocument,
    Applicant,
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
    """Uploads on this file. Reviewing happens on the Applicant documents screen."""

    model = Document
    fields = ("name", "status_label", "review_link", "uploaded_at")
    readonly_fields = fields
    ordering = ("uploaded_at",)
    verbose_name_plural = "Documents (review them on the Applicant documents screen)"

    @admin.display(description="Status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), DOCUMENT_TONE.get(obj.status, "wait"))

    @admin.display(description="")
    def review_link(self, obj):
        return button_link(reverse("admin:applications_document_change", args=[obj.pk]), "Review")


class AgentDocumentInline(ReadOnlyInline):
    """Uploads on an agent application. Reviewing happens on the Agent application documents screen."""

    model = Document
    fields = ("name", "status_label", "review_link", "uploaded_at")
    readonly_fields = fields
    ordering = ("uploaded_at",)
    verbose_name_plural = "Documents (review them on the Agent application documents screen)"

    @admin.display(description="Status")
    def status_label(self, obj):
        return pill(obj.get_status_display(), DOCUMENT_TONE.get(obj.status, "wait"))

    @admin.display(description="")
    def review_link(self, obj):
        return button_link(reverse("admin:applications_agentdocument_change", args=[obj.pk]), "Review")


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


def application_admin_url(application_id, agent_filed):
    """The admin page for an application, on whichever screen owns it."""
    model = "agentapplication" if agent_filed else "application"
    return reverse(f"admin:applications_{model}_change", args=[application_id])


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


# ── Applicants (Every applicant who registered) ───────────────────────


@admin.register(Applicant)
class ApplicantAdmin(AccountDeleteMixin, RealDataOnlyAdmin, admin.ModelAdmin):
    """Every applicant who registered on the portal.

    Provides admissions desk with a complete view of registered applicants,
    their current application state, and direct access to verify their uploaded documents.
    """

    test_user_paths = ("",)

    list_display = (
        "applicant_name",
        "email",
        "phone",
        "application_link",
        "document_button",
        "date_joined",
    )
    search_fields = ("full_name", "email", "phone")
    list_filter = ("email_verified", "is_active", "date_joined")
    ordering = ("-date_joined",)
    list_per_page = 40
    date_hierarchy = "date_joined"
    actions = ("action_send_custom_message",)

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(role=User.Role.APPLICANT)
            .prefetch_related("applications__documents", "draft__files")
            .order_by("-date_joined")
        )

    @admin.display(description="Applicant", ordering="full_name")
    def applicant_name(self, obj):
        return format_html("<strong>{}</strong>", obj.full_name or obj.email)

    @admin.display(description="Application")
    def application_link(self, obj):
        app = obj.applications.first()
        if app:
            return format_html(
                '<a href="{}">{} · {}</a>',
                reverse("admin:applications_application_change", args=[app.pk]),
                app.reference,
                pill(app.get_status_display(), STATUS_TONE.get(app.status, "wait")),
            )
        if hasattr(obj, "draft") and obj.draft:
            return pill(f"Draft (step {obj.draft.current_step})", "info")
        return muted("No application yet")

    @admin.display(description="Application Document")
    def document_button(self, obj):
        app = obj.applications.first()
        if app:
            docs = list(app.documents.all())
            if docs:
                pending = sum(1 for d in docs if d.status == Document.Status.PENDING)
                total = len(docs)
                url = reverse("admin:applications_document_changelist") + f"?application={app.pk}"
                label = f"Application Document ({pending} to review)" if pending else f"Application Document ({total})"
                return button_link(url, label, primary=bool(pending))
            return muted("No documents uploaded")
        if hasattr(obj, "draft") and obj.draft:
            count = obj.draft.files.count()
            if count:
                return muted(f"In draft ({count} files)")
        return muted("No documents")

    @admin.action(description="Send custom message (with attachment)")
    def action_send_custom_message(self, request, queryset):
        """Send a custom message with optional attachments to the selected applicants."""
        from apps.accounts.emails import extract_attachments, send_custom_message_email

        if request.POST.get("apply") == "send_custom_message":
            selected_pks = request.POST.getlist("_selected_action") or request.POST.getlist("recipients")
            users = []
            if selected_pks:
                users = list(
                    User.objects.filter(pk__in=selected_pks)
                    .exclude(email="")
                    .exclude(email__isnull=True)
                )
            else:
                users = [u for u in queryset if u.email]

            if not users:
                self.message_user(request, "No valid applicant recipients found.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(request, "Subject and message are both required.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            attachments = extract_attachments(request)
            sent_count = 0
            failed_count = 0

            for user in users:
                if send_custom_message_email(user, subject, message_body, attachments=attachments, wait=True):
                    sent_count += 1
                    app = Application.objects.filter(applicant=user).order_by("-submitted_at").first()
                    if app:
                        services.notify(app, f"Custom message sent: {subject}", send_email=False)
                else:
                    failed_count += 1

            att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            if sent_count:
                self.message_user(
                    request,
                    f"Custom message{att_info} emailed to {sent_count} applicant(s).",
                    messages.SUCCESS,
                )
            if failed_count:
                self.message_user(
                    request,
                    f"Failed to email {failed_count} applicant(s). Check mail server logs.",
                    messages.ERROR,
                )
            return HttpResponseRedirect(reverse("admin:applications_applicant_changelist"))

        seen_emails = set()
        users = []
        for u in queryset:
            email = (u.email or "").strip().lower()
            if email and email not in seen_emails:
                seen_emails.add(email)
                users.append(u)

        if not users:
            self.message_user(request, "None of the selected applicants have a valid email address.", messages.WARNING)
            return None

        return render(
            request,
            "admin/accounts/send_custom_message_intermediate.html",
            {
                "title": "Send custom message to applicants",
                "recipients": users,
                "action_name": "action_send_custom_message",
                "back_url": reverse("admin:applications_applicant_changelist"),
                "breadcrumb_title": "Applicants",
            },
        )


# ── Applications ────────────────────────────────────────────────────────


@admin.register(Application)
class ApplicationAdmin(RealDataOnlyAdmin, PlainSelectsMixin, admin.ModelAdmin):
    test_user_paths = ("applicant", "submitted_by_agent__user")

    list_display = (
        "reference",
        "full_name",
        "university",
        "verification",
        "application_document_button",
        "stage",
        "status_label",
        "submitted_at",
    )
    list_filter = (
        "status",
        "verification_status",
        DocumentsToReviewFilter,
        "destination_country",
    )
    search_fields = ("reference", "full_name", "email", "institution__name", "custom_course_name")
    autocomplete_fields = ("institution", "applicant")
    filter_horizontal = ("programs",)
    date_hierarchy = "submitted_at"
    list_per_page = 40
    inlines = (DocumentInline, LetterInline, CorrectionInline, StageInline, NotificationInline)

    def get_model_perms(self, request):
        # Managed directly via Applicants, so kept out of the main menu.
        return {}

    readonly_fields = (
        "reference",
        "applicant",
        "submitted_by_agent",
        "status",
        "visa_status",
        "verification_status",
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
                    ("payment_verified", "documents_verified"),
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
        "action_flag_action_required",
        "action_send_to_institution",
        "action_mark_admitted",
        "action_mark_rejected",
        "action_send_custom_message",
        "action_send_email_to_applicants",
    )

    # Applications applicants made themselves. Agent-filed files have their
    # own screen, AgentApplicationAdmin, which flips this. None lists both, for
    # the Test accounts screen.
    filed_by_agent = False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        match = getattr(request, "resolver_match", None)
        # The letter form's application picker searches every file, so it
        # must not be limited to one screen's half.
        if not (match and match.url_name == "autocomplete") and self.filed_by_agent is not None:
            if not self.filed_by_agent:
                from apps.accounts.models import User
                from apps.partners.models import AgentProfile

                agent_emails = AgentProfile.objects.values_list("user__email", flat=True)
                agent_phones = AgentProfile.objects.exclude(user__phone="").values_list("user__phone", flat=True)
                agent_names = AgentProfile.objects.exclude(user__full_name="").values_list("user__full_name", flat=True)
                agent_user_ids = AgentProfile.objects.values_list("user_id", flat=True)

                queryset = (
                    queryset
                    .filter(submitted_by_agent__isnull=True)
                    .filter(applicant__role=User.Role.APPLICANT)
                    .filter(applicant__agent_profile__isnull=True)
                    .exclude(applicant_id__in=agent_user_ids)
                    .exclude(email__in=agent_emails)
                    .exclude(phone__in=agent_phones)
                    .exclude(full_name__in=agent_names)
                )
            else:
                queryset = queryset.filter(submitted_by_agent__isnull=False)
        return (
            queryset
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

    @admin.display(description="Application Document")
    def application_document_button(self, obj):
        if not obj.total_docs:
            return muted("No documents")
        url = reverse("admin:applications_document_changelist") + f"?application={obj.pk}"
        count_label = f" ({obj.pending_docs} to review)" if obj.pending_docs else f" ({obj.total_docs})"
        return button_link(url, f"Application Document{count_label}", primary=bool(obj.pending_docs))

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

    @admin.action(description="Flag: needs action from the applicant")
    def action_flag_action_required(self, request, queryset):
        self._run(
            request, queryset,
            lambda a: services.flag_action_required(a, verified_by=request.user),
            "flagged as needing action", "already flagged", messages.WARNING,
        )

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

    @admin.action(description="Send custom message (with attachment)")
    def action_send_custom_message(self, request, queryset):
        """Send a custom message with optional attachments to the selected applicants."""
        from apps.accounts.emails import extract_attachments, send_custom_message_email
        from apps.accounts.models import User
        from django.http import HttpResponseRedirect
        from django.shortcuts import render
        from django.urls import reverse

        if request.POST.get("apply") == "send_custom_message":
            selected_pks = request.POST.getlist("_selected_action") or request.POST.getlist("recipients")
            users = []
            if selected_pks:
                users = list(
                    User.objects.filter(pk__in=selected_pks)
                    .exclude(email="")
                    .exclude(email__isnull=True)
                )
                if not users:
                    apps = list(Application.objects.filter(pk__in=selected_pks).select_related("applicant"))
                    users = [a.applicant for a in apps if a.applicant and a.applicant.email]
            else:
                users = [a.applicant for a in queryset.select_related("applicant") if a.applicant and a.applicant.email]

            seen_emails = set()
            unique_users = []
            for u in users:
                email = (u.email or "").strip().lower()
                if email and email not in seen_emails:
                    seen_emails.add(email)
                    unique_users.append(u)

            if not unique_users:
                self.message_user(request, "No valid applicant recipients found. Please go back and try again.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(request, "Subject and message are both required.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            attachments = extract_attachments(request)
            sent_count = 0
            failed_count = 0

            for user in unique_users:
                if send_custom_message_email(user, subject, message_body, attachments=attachments, wait=True):
                    sent_count += 1
                    app = Application.objects.filter(applicant=user).order_by("-submitted_at").first()
                    if app:
                        services.notify(app, f"Message from Gabstep: {subject}. {message_body}", send_email=False)
                else:
                    failed_count += 1

            att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            if sent_count:
                self.message_user(
                    request,
                    f"Custom message{att_info} emailed to {sent_count} applicant(s).",
                    messages.SUCCESS,
                )
            if failed_count:
                self.message_user(
                    request,
                    f"Failed to email {failed_count} applicant(s). Check mail server logs.",
                    messages.ERROR,
                )
            changelist_url = reverse(
                "admin:applications_agentapplication_changelist"
                if self.filed_by_agent
                else "admin:applications_application_changelist"
            )
            return HttpResponseRedirect(changelist_url)

        # Step 1: collect applicant users from selected applications
        seen_emails = set()
        users = []
        for app in queryset.select_related("applicant"):
            u = app.applicant
            email = (u.email if u and u.email else app.email).strip().lower()
            if email and email not in seen_emails and u:
                seen_emails.add(email)
                users.append(u)

        if not users:
            self.message_user(request, "None of the selected applications have a valid applicant email address.", messages.WARNING)
            return None

        back_url = reverse(
            "admin:applications_agentapplication_changelist"
            if self.filed_by_agent
            else "admin:applications_application_changelist"
        )
        return render(
            request,
            "admin/accounts/send_custom_message_intermediate.html",
            {
                "title": "Send custom message to applicants",
                "recipients": users,
                "action_name": "action_send_custom_message",
                "back_url": back_url,
                "breadcrumb_title": "Agent applications" if self.filed_by_agent else "Applicant applications",
            },
        )

    @admin.action(description="Email a message")
    def action_send_email_to_applicants(self, request, queryset):
        """Write to the owner of each file: the applicant, or the agent who filed it."""
        from apps.accounts.emails import extract_attachments

        if request.POST.get("apply") == "send_email":
            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(request, "Subject and message are both required.", messages.ERROR)
                return None
            attachments = extract_attachments(request)
            for application in queryset:
                services.send_applicant_email_message(application, subject, message_body, attachments=attachments)
            att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            self.message_user(
                request,
                f"Message{att_info} sent for {plural(queryset.count(), 'application')}.",
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
class DocumentAdmin(RealDataOnlyAdmin, admin.ModelAdmin):
    """Open a document, look at it, then Verify it or Reject it with a comment."""

    test_user_paths = ("application__applicant", "application__submitted_by_agent__user")

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

    def get_model_perms(self, request):
        # Managed directly via the Application Document button, so kept out of the main menu.
        return {}

    def get_queryset(self, request):
        # Waiting for review first, then the rest.
        waiting_first = Case(When(status=Document.Status.PENDING, then=0), default=1, output_field=IntegerField())
        qs = (
            super()
            .get_queryset(request)
            .filter(application__submitted_by_agent__isnull=True)
            .order_by(waiting_first, "-uploaded_at")
        )
        app_id = request.GET.get("application") or request.GET.get("application_id")
        if app_id:
            qs = qs.filter(application_id=app_id)
        applicant_id = request.GET.get("applicant") or request.GET.get("applicant_id")
        if applicant_id:
            qs = qs.filter(application__applicant_id=applicant_id)
        return qs

    def changelist_view(self, request, extra_context=None):
        extra = {**(extra_context or {})}
        if "title" not in extra:
            app_id = request.GET.get("application") or request.GET.get("application_id")
            applicant_id = request.GET.get("applicant") or request.GET.get("applicant_id")
            if app_id:
                app = Application.objects.filter(pk=app_id).select_related("applicant").first()
                if app:
                    extra["title"] = f"Application documents for {app.full_name} ({app.reference})"
            elif applicant_id:
                user = User.objects.filter(pk=applicant_id).first()
                if user:
                    extra["title"] = f"Application documents for {user.full_name or user.email}"
        return super().changelist_view(request, extra)

    @admin.display(description="Applicant", ordering="application__full_name")
    def applicant(self, obj):
        return f"{obj.application.full_name} · {obj.application.reference}"

    @admin.display(description="Application")
    def application_link(self, obj):
        return format_html(
            '<a href="{}">{} · {}</a>',
            application_admin_url(obj.application_id, obj.application.submitted_by_agent_id is not None),
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
        info = self.opts.app_label, self.opts.model_name
        return button_link(reverse(f"admin:{info[0]}_{info[1]}_change", args=[obj.pk]), "Review")

    # One page per decision.
    def get_urls(self):
        info = self.opts.app_label, self.opts.model_name
        return [
            path("<int:pk>/verify/", self.admin_site.admin_view(self.verify_view), name=f"{info[0]}_{info[1]}_verify"),
            path("<int:pk>/reject/", self.admin_site.admin_view(self.reject_view), name=f"{info[0]}_{info[1]}_reject"),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        document = get_object_or_404(self.get_queryset(request), pk=object_id)
        url = document.file.url if document.file else ""
        name = (document.original_filename or document.file.name if document.file else "").lower()
        info = self.opts.app_label, self.opts.model_name
        agent = getattr(document.application, "submitted_by_agent", None)
        agent_name = (agent.user.full_name or agent.user.email) if agent else None
        extra_context = {
            **(extra_context or {}),
            "title": f"Review {self.opts.verbose_name}",
            "doc": document,
            "agent_name": agent_name,
            "file_url": url,
            "is_pdf": name.endswith(".pdf"),
            "is_image": name.endswith((".jpg", ".jpeg", ".png", ".webp")),
            "verify_url": reverse(f"admin:{info[0]}_{info[1]}_verify", args=[document.pk]),
            "reject_url": reverse(f"admin:{info[0]}_{info[1]}_reject", args=[document.pk]),
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def verify_view(self, request, pk):
        document = get_object_or_404(self.get_queryset(request), pk=pk)
        info = self.opts.app_label, self.opts.model_name
        if request.method == "POST":
            services.verify_documents([document], reviewed_by=request.user)
            self.message_user(request, f"{document.name} verified. The applicant has been told.", messages.SUCCESS)
        return HttpResponseRedirect(
            reverse(f"admin:{info[0]}_{info[1]}_changelist") + f"?application={document.application_id}"
        )

    def reject_view(self, request, pk):
        document = get_object_or_404(self.get_queryset(request), pk=pk)
        info = self.opts.app_label, self.opts.model_name
        changelist_url = reverse(f"admin:{info[0]}_{info[1]}_changelist") + f"?application={document.application_id}"
        change_url = reverse(f"admin:{info[0]}_{info[1]}_change", args=[document.pk])
        form = RejectDocumentForm(request.POST or None, initial={"note": document.review_note})
        if request.method == "POST" and form.is_valid():
            services.reject_document(document, form.cleaned_data["note"], reviewed_by=request.user)
            self.message_user(
                request,
                f"{document.name} rejected. Your comment was emailed and is shown in their dashboard.",
                messages.WARNING,
            )
            return HttpResponseRedirect(changelist_url)
        return render(
            request,
            "admin/applications/document/reject.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Reject {document.name}",
                "doc": document,
                "form": form,
                "opts": self.model._meta,
                "back_url": change_url,
                "changelist_url": changelist_url,
                "changelist_title": self.model._meta.verbose_name_plural.title(),
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
class LetterAdmin(RealDataOnlyAdmin, PlainSelectsMixin, admin.ModelAdmin):
    """Issue a letter: choose the application, upload the file, save.

    Saving a new letter publishes it straight away and emails the owner of the
    file (the agent, for a student an agent registered). Unpublish hides one;
    Publish shows it again.
    """

    test_user_paths = ("application__applicant", "application__submitted_by_agent__user")

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
            "description": "Saving a new letter publishes it and emails the applicant, or the agent for an agent's student. Use Unpublish on the Letters list to hide one.",
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
        from django.utils import timezone

        if obj.issued_by_id is None:
            obj.issued_by = request.user
        announce = not change and obj.is_published
        if announce:
            obj.issued_at = obj.issued_at or timezone.now()
        super().save_model(request, obj, form, change)
        if announce:
            services.announce_letter(obj)
            self.message_user(request, "Letter published and emailed.", messages.SUCCESS)

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
class CorrectionRequestAdmin(RealDataOnlyAdmin, admin.ModelAdmin):
    """Approve a requested change (written to the file where possible) or decline it."""

    test_user_paths = ("application__applicant", "application__submitted_by_agent__user")

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
class VisaSupportApplicationAdmin(RealDataOnlyAdmin, admin.ModelAdmin):
    """Admitted students, and anyone who sent their letter to the visa desk."""

    test_user_paths = ("applicant", "submitted_by_agent__user")

    list_display = ("reference", "full_name", "filed_by", "institution", "sent_by_applicant", "visa_label", "confirm_link")
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
    actions = ("action_start_visa_processing",)

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(Q(status=Application.Status.ADMITTED) | Q(transferred_to_visa_support=True))
            .select_related("institution", "destination_country", "submitted_by_agent__user")
            .prefetch_related("letters", "programs")
        )

    @admin.display(description="Filed by")
    def filed_by(self, obj):
        agent = obj.submitted_by_agent
        return (agent.user.full_name or agent.user.email) if agent else muted("Applicant")

    @admin.display(description="")
    def confirm_link(self, obj):
        if obj.visa_status == Application.VisaStatus.COMPLETED:
            return pill("Done", "ok")
        return button_link(
            reverse("admin:applications_visasupportapplication_confirm", args=[obj.pk]),
            "Confirm visa support done",
            primary=True,
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/confirm/",
                self.admin_site.admin_view(self.confirm_view),
                name="applications_visasupportapplication_confirm",
            ),
        ] + super().get_urls()

    @staticmethod
    def _commission_text(application):
        """The visa commission just paid, in the currency it was paid in."""
        from apps.partners.currency import money
        from apps.partners.models import Commission

        commission = Commission.objects.filter(application=application, kind=Commission.Kind.VISA).first()
        return money(commission.amount, commission.currency) if commission else "The commission"

    def confirm_view(self, request, pk):
        """One job: confirm visa support is done. Asks first, because it pays the agent."""
        application = get_object_or_404(self.get_queryset(request), pk=pk)
        changelist = reverse("admin:applications_visasupportapplication_changelist")
        if request.method == "POST":
            changed, paid = services.mark_visa_verified(application)
            if changed:
                self.message_user(
                    request,
                    f"Visa support confirmed for {application.full_name}."
                    + (f" {self._commission_text(application)} credited to the agent, who has been emailed." if paid else ""),
                    messages.SUCCESS,
                )
            else:
                self.message_user(request, "That visa support was already confirmed.", messages.INFO)
            return HttpResponseRedirect(changelist)
        agent = application.submitted_by_agent
        return render(
            request,
            "admin/applications/visasupportapplication/confirm.html",
            {
                **self.admin_site.each_context(request),
                "title": "Confirm visa support is done",
                "application": application,
                "agent": agent,
                "pays": bool(agent) and not application.commissions.filter(kind="visa").exists(),
                "opts": self.model._meta,
                "back_url": changelist,
            },
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


# ── Agent applications ──────────────────────────────────────────────────
# Opens as a list of agents. Clicking an agent lists only the students that
# agent registered; each row ends with one download of everything on the file.


class AgentFilter(admin.SimpleListFilter):
    title = "agent"
    parameter_name = "agent"

    def lookups(self, request, model_admin):
        from apps.partners.models import AgentProfile

        # Real agents on the working screen, test agents under Test accounts.
        is_test = getattr(model_admin, "test_data_only", False)
        agents = AgentProfile.objects.filter(user__is_test_account=is_test)
        return [
            (agent.pk, agent.user.full_name or agent.user.email)
            for agent in agents.select_related("user").order_by("user__full_name")
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(submitted_by_agent_id=self.value())
        return queryset


PAYMENT_TONE = {"paid": "ok", "waived": "info", "review": "wait", "failed": "bad"}


@admin.register(AgentApplications)
class AgentApplicationsAdmin(RealDataOnlyAdmin, admin.ModelAdmin):
    """Every partner agent. Click an agent to see the students they registered."""

    test_user_paths = ("user",)

    list_display = ("agent", "email", "code", "students", "awaiting_payment", "open_link")
    search_fields = ("user__full_name", "user__email", "agency_name")
    list_display_links = None
    list_per_page = 50

    def get_model_perms(self, request):
        # Kept out of the Applications admin menu so the section is strictly applicant-focused.
        return {}

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user")
            .annotate(
                student_count=Count("applications", distinct=True),
                awaiting_count=Count(
                    "applications", filter=Q(applications__payment__status="review"), distinct=True
                ),
            )
            .order_by("-student_count", "user__full_name")
        )

    def _students_url(self, obj):
        return reverse("admin:applications_agentapplication_changelist") + f"?agent={obj.pk}"

    @admin.display(description="Agent", ordering="user__full_name")
    def agent(self, obj):
        return format_html('<a href="{}"><strong>{}</strong></a>', self._students_url(obj), obj.user.full_name or obj.user.email)

    @admin.display(description="Email", ordering="user__email")
    def email(self, obj):
        return obj.user.email

    @admin.display(description="Code")
    def code(self, obj):
        return obj.partner_code

    @admin.display(description="Students", ordering="student_count")
    def students(self, obj):
        return obj.student_count

    @admin.display(description="Payments to confirm", ordering="awaiting_count")
    def awaiting_payment(self, obj):
        return pill(str(obj.awaiting_count), "wait") if obj.awaiting_count else muted("None")

    @admin.display(description="")
    def open_link(self, obj):
        return button_link(self._students_url(obj), "View students", primary=True)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return HttpResponseRedirect(
            reverse("admin:applications_agentapplication_changelist") + f"?agent={object_id}"
        )


class DocumentAgentFilter(admin.SimpleListFilter):
    title = "agent"
    parameter_name = "agent"

    def lookups(self, request, model_admin):
        from apps.partners.models import AgentProfile

        agents = AgentProfile.objects.filter(user__is_test_account=False)
        return [
            (agent.pk, agent.user.full_name or agent.user.email)
            for agent in agents.select_related("user").order_by("user__full_name")
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(application__submitted_by_agent_id=self.value())
        return queryset


@admin.register(AgentDocument)
class AgentDocumentAdmin(DocumentAdmin):
    """Review documents uploaded on agent-filed student applications."""

    list_display = ("name", "applicant", "agent", "status_label", "uploaded_at", "open_link")
    list_filter = (DocumentAgentFilter, "status", "kind", "uploaded_at")
    search_fields = (
        "name",
        "original_filename",
        "application__reference",
        "application__full_name",
        "application__submitted_by_agent__user__full_name",
        "application__submitted_by_agent__user__email",
    )
    list_select_related = ("application", "application__submitted_by_agent__user")

    def get_queryset(self, request):
        waiting_first = Case(When(status=Document.Status.PENDING, then=0), default=1, output_field=IntegerField())
        qs = (
            super(DocumentAdmin, self)
            .get_queryset(request)
            .filter(application__submitted_by_agent__isnull=False)
            .order_by(waiting_first, "-uploaded_at")
        )
        app_id = request.GET.get("application") or request.GET.get("application_id")
        if app_id:
            qs = qs.filter(application_id=app_id)
        return qs

    def changelist_view(self, request, extra_context=None):
        extra = {**(extra_context or {})}
        app_id = request.GET.get("application") or request.GET.get("application_id")
        if app_id:
            app = Application.objects.filter(pk=app_id).first()
            if app:
                extra["title"] = f"Agent application documents for {app.full_name} ({app.reference})"
        return super().changelist_view(request, extra)

    @admin.display(description="Agent", ordering="application__submitted_by_agent__user__full_name")
    def agent(self, obj):
        agent = obj.application.submitted_by_agent
        if not agent:
            return muted("—")
        name = agent.user.full_name or agent.user.email
        return format_html(
            '<a href="{}"><strong>{}</strong></a>',
            reverse("admin:partners_agentprofile_change", args=[agent.pk]),
            name,
        )


@admin.register(AgentApplication)
class AgentApplicationAdmin(ApplicationAdmin):
    """Applications filed by partner agents."""

    filed_by_agent = True
    inlines = (AgentDocumentInline, LetterInline, CorrectionInline, StageInline, NotificationInline)
    list_display = (
        "reference",
        "full_name",
        "agent",
        "university",
        "application_document_button",
        "payment_state",
        "verification",
        "status_label",
        "submitted_at",
        "download",
    )
    list_filter = (AgentFilter, "status", "verification_status", DocumentsToReviewFilter, "destination_country")
    search_fields = (
        "reference",
        "full_name",
        "email",
        "institution__name",
        "custom_course_name",
        "submitted_by_agent__user__full_name",
        "submitted_by_agent__user__email",
        "submitted_by_agent__agency_name",
    )

    def has_add_permission(self, request):
        return False

    def get_model_perms(self, request):
        return admin.ModelAdmin.get_model_perms(self, request)

    def changelist_view(self, request, extra_context=None):
        from apps.partners.models import AgentProfile

        agent = AgentProfile.objects.select_related("user").filter(pk=request.GET.get("agent") or 0).first()
        title = (
            f"Students registered by {agent.user.full_name or agent.user.email}"
            if agent
            else "Agent applications"
        )
        return super().changelist_view(request, {**(extra_context or {}), "title": title})

    @admin.display(description="Agent", ordering="submitted_by_agent__user__full_name")
    def agent(self, obj):
        agent = obj.submitted_by_agent
        if not agent:
            return muted("—")
        name = agent.user.full_name or agent.user.email
        return format_html(
            '<a href="{}"><strong>{}</strong></a>',
            reverse("admin:partners_agentprofile_change", args=[agent.pk]),
            name,
        )

    @admin.display(description="Application Document")
    def application_document_button(self, obj):
        total = obj.documents.count()
        pending = obj.documents.filter(status=Document.Status.PENDING).count()
        if not total:
            return muted("No documents")
        url = reverse("admin:applications_agentdocument_changelist") + f"?application={obj.pk}"
        count_label = f" ({pending} to review)" if pending else f" ({total})"
        return button_link(url, f"Application Document{count_label}", primary=bool(pending))

    @admin.display(description="Payment")
    def payment_state(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return muted("Not paid")
        return pill(payment.get_status_display(), PAYMENT_TONE.get(payment.status, "idle"))

    @admin.display(description="")
    def download(self, obj):
        return button_link(
            reverse("admin:applications_agentapplication_download", args=[obj.pk]), "Download"
        )

    def get_urls(self):
        return [
            path(
                "<int:pk>/download/",
                self.admin_site.admin_view(self.download_view),
                name="applications_agentapplication_download",
            ),
        ] + super().get_urls()

    def download_view(self, request, pk):
        from django.http import HttpResponse

        from .dossier import dossier_zip

        application = get_object_or_404(
            Application.objects.filter(submitted_by_agent__isnull=False)
            .select_related("institution", "origin_country", "destination_country", "payment", "submitted_by_agent__user")
            .prefetch_related("programs", "documents"),
            pk=pk,
        )
        filename, data = dossier_zip(application)
        response = HttpResponse(data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
