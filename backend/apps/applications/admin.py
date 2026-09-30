"""The admissions desk.

The admin is where staff actually work the pipeline: verify documents, move a
file to the next stage, approve a correction, and upload the offer letter the
applicant is waiting for. Every action here goes through ``services`` so the
admin and the partner API cannot disagree about what a milestone does, and every
action that changes something the applicant can see writes them a notification.
"""

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from . import services
from .models import (
    Application,
    ApplicationDraft,
    CorrectionRequest,
    Document,
    Letter,
    Notification,
    Stage,
    VisaSupportApplication,
)


def _plural(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"


class StageInline(admin.TabularInline):
    """The five-stage track, editable in place.

    This is the manual path: set a stage to In progress and the applicant's ring
    moves with it. The bulk actions on the changelist are the quicker route for
    the common milestones.
    """

    model = Stage
    extra = 0
    fields = ("order", "name", "status", "eta", "note")
    ordering = ("order",)


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    fields = ("name", "kind", "preview", "status", "uploaded_at")
    readonly_fields = ("preview", "uploaded_at")
    ordering = ("uploaded_at",)

    @admin.display(description="File")
    def preview(self, obj):
        if not obj.file:
            return "None"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a> <span style="color:#6b7280">({})</span>',
            obj.file.url,
            obj.original_filename or "Open",
            obj.human_size,
        )


class LetterInline(admin.StackedInline):
    """Upload an offer letter here and the applicant sees it on their dashboard."""

    model = Letter
    extra = 0
    fk_name = "application"
    fields = ("kind", "title", "file", "note", "is_published", "issued_at")
    readonly_fields = ()


class CorrectionInline(admin.TabularInline):
    model = CorrectionRequest
    extra = 0
    can_delete = False
    fields = ("ticket", "field", "current_value", "corrected_value", "status", "created_at")
    readonly_fields = ("ticket", "field", "current_value", "corrected_value", "created_at")
    ordering = ("-created_at",)


class NotificationInline(admin.TabularInline):
    """What the applicant has been told, newest first. Read-only on purpose:
    the feed is a record of what happened, not somewhere to write history."""

    model = Notification
    extra = 0
    can_delete = False
    fields = ("text", "is_read", "created_at")
    readonly_fields = ("text", "is_read", "created_at")
    ordering = ("-created_at",)
    max_num = 0


class HasLetterFilter(admin.SimpleListFilter):
    title = "offer letter"
    parameter_name = "has_letter"

    def lookups(self, request, model_admin):
        return (("yes", "Issued"), ("no", "Not issued"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(letters__is_published=True).distinct()
        if self.value() == "no":
            return queryset.exclude(letters__is_published=True)
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


class VerificationStatusFilter(admin.SimpleListFilter):
    title = "verification audit"
    parameter_name = "audit_status"

    def lookups(self, request, model_admin):
        return (
            ("unverified", "⚠️ Unverified (Pending Review)"),
            ("in_review", "🔍 In Review"),
            ("verified", "✓ Verified & Approved"),
            ("action_required", "❌ Action Required"),
        )

    def queryset(self, request, queryset):
        if self.value() == "unverified":
            return queryset.filter(
                Q(verification_status=Application.VerificationStatus.UNVERIFIED)
                | (
                    Q(personal_details_verified=False)
                    | Q(academic_details_verified=False)
                    | Q(documents_verified=False)
                    | Q(payment_verified=False)
                )
            ).distinct()
        if self.value() == "in_review":
            return queryset.filter(verification_status=Application.VerificationStatus.IN_REVIEW)
        if self.value() == "verified":
            return queryset.filter(verification_status=Application.VerificationStatus.VERIFIED)
        if self.value() == "action_required":
            return queryset.filter(verification_status=Application.VerificationStatus.ACTION_REQUIRED)
        return queryset


class HasOpenCorrectionFilter(admin.SimpleListFilter):
    title = "Correction requests"
    parameter_name = "has_corrections"

    def lookups(self, request, model_admin):
        return (
            ("open", "⚠️ Has open correction request"),
            ("resolved", "Resolved corrections only"),
            ("any", "Any correction requested"),
            ("none", "No corrections"),
        )

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(corrections__status=CorrectionRequest.Status.OPEN).distinct()
        if self.value() == "resolved":
            return (
                queryset.filter(corrections__isnull=False)
                .exclude(corrections__status=CorrectionRequest.Status.OPEN)
                .distinct()
            )
        if self.value() == "any":
            return queryset.filter(corrections__isnull=False).distinct()
        if self.value() == "none":
            return queryset.filter(corrections__isnull=True)
        return queryset


class CustomCourseFilter(admin.SimpleListFilter):
    title = "course selection type"
    parameter_name = "course_type"

    def lookups(self, request, model_admin):
        return (
            ("custom", "✍️ Self-Inputted Course (Reach out)"),
            ("catalog", "Standard Partner Catalog"),
        )

    def queryset(self, request, queryset):
        if self.value() == "custom":
            return queryset.filter(is_custom_course=True)
        if self.value() == "catalog":
            return queryset.filter(is_custom_course=False)
        return queryset


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "full_name",
        "course_selection_badge",
        "correction_badge",
        "verification_badge",
        "destination_country",
        "stage_badge",
        "status_badge",
        "visa_badge",
        "letter_badge",
        "submitted_at",
    )
    list_filter = (
        CustomCourseFilter,
        HasOpenCorrectionFilter,
        VerificationStatusFilter,
        "verification_status",
        "personal_details_verified",
        "academic_details_verified",
        "documents_verified",
        "payment_verified",
        "status",
        "visa_status",
        "transferred_to_visa_support",
        "destination_country",
        HasLetterFilter,
        FiledByFilter,
    )
    search_fields = (
        "reference",
        "full_name",
        "email",
        "institution__name",
        "custom_course_name",
    )
    autocomplete_fields = ("institution", "applicant")
    filter_horizontal = ("programs",)
    date_hierarchy = "submitted_at"
    list_per_page = 40
    save_on_top = True
    inlines = (StageInline, LetterInline, DocumentInline, CorrectionInline, NotificationInline)
    readonly_fields = (
        "reference",
        "custom_course_alert",
        "is_custom_course",
        "custom_course_name",
        "verification_status",
        "verified_at",
        "verified_by",
        "submitted_at",
        "created_at",
        "updated_at",
        "transferred_to_visa_support_at",
        "payment_summary",
    )

    fieldsets = (
        (
            "Admissions Verification Audit",
            {
                "description": (
                    "Tick each check once that part of the file has been reviewed. "
                    "The overall status follows from the four checks: all four ticked "
                    "means Verified. Ticking uploaded documents also marks every "
                    "uploaded file as Verified."
                ),
                "fields": (
                    ("verification_status", "verified_at"),
                    (
                        "personal_details_verified",
                        "academic_details_verified",
                        "documents_verified",
                        "payment_verified",
                    ),
                    ("verified_by", "verification_notes"),
                ),
            },
        ),
        (
            "Application",
            {
                "fields": (
                    "reference",
                    "applicant",
                    "submitted_by_agent",
                    ("status", "visa_status"),
                    ("transferred_to_visa_support", "transferred_to_visa_support_at"),
                    "payment_summary",
                )
            },
        ),
        (
            "Applicant",
            {
                "fields": (
                    ("full_name", "email"),
                    ("phone", "address"),
                    ("origin_country", "destination_country"),
                )
            },
        ),
        (
            "Academic",
            {
                "fields": (
                    "previous_schools",
                    ("qualification", "year_graduated", "grade_gpa"),
                )
            },
        ),
        (
            "Programme & Course Choice",
            {
                "fields": (
                    "custom_course_alert",
                    ("is_custom_course", "custom_course_name"),
                    "institution",
                    "programs",
                )
            },
        ),
        ("Internal", {"fields": ("notes", "submitted_at", "created_at", "updated_at")}),
    )

    actions = (
        # Verification: one action per check.
        "action_verify_personal",
        "action_verify_academic",
        "action_verify_documents",
        "action_verify_payment",
        "action_flag_action_required",
        "action_reset_verification",
        # Pipeline: one action per milestone.
        "action_send_to_institution",
        "action_mark_admitted",
        "action_mark_rejected",
        "action_transfer_to_visa_desk",
        # Talking to the applicant.
        "action_send_email_to_applicants",
        "action_resend_login",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("institution", "destination_country", "submitted_by_agent")
            .prefetch_related("stages", "letters")
            .annotate(letter_count=Count("letters", distinct=True))
        )

    def save_model(self, request, obj, form, change):
        checkpoint_changed = [
            key
            for key, (field, _) in services.CHECKPOINTS.items()
            if field in form.changed_data
        ]
        if change and checkpoint_changed:
            services._refresh_verification_status(obj, verified_by=request.user)

        super().save_model(request, obj, form, change)
        if not change:
            return

        if "documents" in checkpoint_changed and obj.documents_verified:
            obj.documents.exclude(status="Verified").update(status="Verified")
        if checkpoint_changed:
            services.notify(
                obj,
                f"Your application verification was updated: {obj.get_verification_status_display()}.",
            )
        if "status" in form.changed_data:
            services.notify(
                obj, f"Your application status was updated to: {obj.get_status_display()}."
            )
        if "visa_status" in form.changed_data:
            services.notify(
                obj, f"Your visa processing status was updated to: {obj.get_visa_status_display()}."
            )
        if "transferred_to_visa_support" in form.changed_data and obj.transferred_to_visa_support:
            services.notify(obj, "Your file has been passed to our Visa Support desk.")

    # ── Display helpers ──────────────────────────────────────────────
    # Colour carries the same meaning here as in the product: green is
    # settled, amber is waiting on someone, red needs attention.

    @staticmethod
    def _pill(text, tone):
        colours = {
            "ok": ("#dcfce7", "#166534"),
            "wait": ("#fef3c7", "#92400e"),
            "bad": ("#fee2e2", "#991b1b"),
            "info": ("#e0e7ff", "#3730a3"),
            "idle": ("#f1f5f9", "#475569"),
        }
        background, colour = colours.get(tone, colours["idle"])
        return format_html(
            '<span style="display:inline-block;padding:2px 9px;border-radius:999px;'
            'background:{};color:{};font-size:11px;font-weight:700;white-space:nowrap">{}</span>',
            background,
            colour,
            text,
        )

    @admin.display(description="Course / Programme")
    def course_selection_badge(self, obj):
        if obj.is_custom_course:
            return format_html(
                '<div style="max-width:240px;">'
                '<span style="display:inline-block;padding:2px 8px;background:#fef3c7;color:#92400e;border:1px solid #fde68a;border-radius:999px;font-weight:700;font-size:11px;margin-bottom:3px;">✍️ Custom Request</span>'
                '<div style="font-weight:700;font-size:12px;color:#1e293b;line-height:1.3;">{}</div>'
                '</div>',
                obj.custom_course_name or "Custom course",
            )
        if obj.institution:
            return format_html(
                '<div style="font-weight:600;font-size:12px;color:#1e293b;line-height:1.3;">{}</div>',
                obj.institution.name,
            )
        return format_html('<span style="color:#94a3b8;font-size:11px;">Not specified</span>')

    @admin.display(description="Applicant Request Notice")
    def custom_course_alert(self, obj):
        if not obj.is_custom_course:
            return format_html('<span style="color:#64748b;">Standard university catalog application.</span>')
        return format_html(
            '<div style="background:#fffbeb;border:2px solid #f59e0b;padding:12px 16px;border-radius:8px;color:#92400e;font-size:13px;line-height:1.5;">'
            '<strong style="font-size:14px;color:#b45309;">✍️ Applicant Inputted Their Own Course:</strong><br/>'
            'Desired Programme: <strong style="color:#9a3412;font-size:14px;">{}</strong><br/>'
            'Destination: <strong>{}</strong><br/>'
            '<p style="margin:8px 0 0 0;color:#78350f;">'
            '<em>No upfront payment was charged for this application. '
            'Admissions staff should reach out directly to the applicant to match them with institutions:</em><br/>'
            '📧 Email: <a href="mailto:{}" style="color:#2563eb;text-decoration:underline;font-weight:700;">{}</a> &nbsp;|&nbsp; '
            '📞 Phone: <a href="tel:{}" style="color:#2563eb;text-decoration:underline;font-weight:700;">{}</a>'
            '</p>'
            '</div>',
            obj.custom_course_name or "N/A",
            obj.destination_country.name if obj.destination_country else "N/A",
            obj.email,
            obj.email,
            obj.phone or "N/A",
            obj.phone or "N/A",
        )

    @admin.display(description="Correction Requests")
    def correction_badge(self, obj):
        open_count = obj.corrections.filter(status=CorrectionRequest.Status.OPEN).count()
        if open_count > 0:
            return format_html(
                '<span style="display:inline-block;padding:2px 10px;background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:999px;font-weight:800;font-size:11px;white-space:nowrap">⚠️ {} Open Request{}</span>',
                open_count,
                "s" if open_count > 1 else "",
            )
        total = obj.corrections.count()
        if total > 0:
            return format_html(
                '<span style="display:inline-block;padding:2px 9px;background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;border-radius:999px;font-weight:600;font-size:11px;white-space:nowrap">{} Resolved</span>',
                total,
            )
        return format_html('<span style="color:#94a3b8;font-size:11px;">None</span>')

    @admin.display(description="Verification", ordering="verification_status")
    def verification_badge(self, obj):
        summary = obj.verification_summary
        status = summary["status"]
        cleared = summary["cleared_count"]
        total = summary["total_count"]

        if status == Application.VerificationStatus.VERIFIED:
            return self._pill("Verified ✓", "ok")
        if status == Application.VerificationStatus.IN_REVIEW:
            return self._pill(f"In Review ({cleared}/{total})", "info")
        if status == Application.VerificationStatus.ACTION_REQUIRED:
            return self._pill("Action Required", "bad")
        return self._pill(f"Unverified ({cleared}/{total})", "wait")

    @admin.display(description="Stage", ordering="status")
    def stage_badge(self, obj):
        stages = list(obj.stages.all())
        if not stages:
            return "None"
        current = obj.current_stage
        position = obj.current_stage_index + 1
        return format_html(
            '<span style="white-space:nowrap">{} <span style="color:#6b7280">· {} of {}</span></span>',
            current.name,
            position,
            len(stages),
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = {
            Application.Status.ADMITTED: "ok",
            Application.Status.REJECTED: "bad",
            Application.Status.IN_REVIEW: "wait",
        }.get(obj.status, "idle")
        return self._pill(obj.get_status_display(), tone)

    @admin.display(description="Visa", ordering="visa_status")
    def visa_badge(self, obj):
        tone = {
            Application.VisaStatus.COMPLETED: "ok",
            Application.VisaStatus.IN_PROGRESS: "wait",
        }.get(obj.visa_status, "idle")
        return self._pill(obj.get_visa_status_display(), tone)

    @admin.display(description="Letter")
    def letter_badge(self, obj):
        published = [letter for letter in obj.letters.all() if letter.is_published]
        if published:
            return self._pill(_plural(len(published), "letter"), "ok")
        if obj.letter_count:
            return self._pill("staged", "wait")
        return self._pill("none", "idle")

    @admin.display(description="Payment")
    def payment_summary(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "No payment recorded."
        link = reverse("admin:payments_payment_change", args=[payment.pk])
        return format_html(
            '{} · {} · <a href="{}">{}</a>',
            payment.display_total,
            payment.get_status_display(),
            link,
            payment.reference,
        )

    # ── Actions ──────────────────────────────────────────────────────
    # One action, one job. They are listed in the order a file is worked:
    # verify each part, move it through the pipeline, then talk to the applicant.
    # Each reports what changed and what it skipped, and why.

    def _run(self, request, queryset, step, done, skipped_reason, level=messages.SUCCESS):
        """Apply ``step`` to each selected file and report the outcome."""
        changed = [a for a in queryset if step(a)]
        skipped = queryset.count() - len(changed)
        if changed:
            self.message_user(request, f"{_plural(len(changed), 'application')} {done}.", level)
        if skipped:
            self.message_user(
                request,
                f"{_plural(skipped, 'application')} skipped: {skipped_reason}.",
                messages.INFO,
            )

    def _verify(self, request, queryset, checkpoint, done):
        self._run(
            request,
            queryset,
            lambda a: services.verify_checkpoint(a, checkpoint, verified_by=request.user),
            done,
            "already verified",
        )

    @admin.action(description="1. Verify personal details")
    def action_verify_personal(self, request, queryset):
        self._verify(request, queryset, "personal", "had personal details verified")

    @admin.action(description="2. Verify academic details")
    def action_verify_academic(self, request, queryset):
        self._verify(request, queryset, "academic", "had academic details verified")

    @admin.action(description="3. Verify uploaded documents")
    def action_verify_documents(self, request, queryset):
        self._verify(request, queryset, "documents", "had every uploaded document verified")

    @admin.action(description="4. Verify application fee")
    def action_verify_payment(self, request, queryset):
        self._verify(request, queryset, "payment", "had the application fee verified")

    @admin.action(description="Flag: needs action from the applicant")
    def action_flag_action_required(self, request, queryset):
        self._run(
            request,
            queryset,
            lambda a: services.flag_action_required(a, verified_by=request.user),
            "flagged as needing action",
            "already flagged",
            messages.WARNING,
        )

    @admin.action(description="Reset verification (clear all four checks)")
    def action_reset_verification(self, request, queryset):
        self._run(
            request,
            queryset,
            services.reset_verification,
            "reset to unverified",
            "nothing to reset",
            messages.WARNING,
        )

    @admin.action(description="Send to institution")
    def action_send_to_institution(self, request, queryset):
        self._run(
            request,
            queryset,
            services.send_to_institution,
            "sent to the institution",
            "documents not verified yet, or the file is already with the institution or decided",
        )

    @admin.action(description="Grant admission")
    def action_mark_admitted(self, request, queryset):
        self._run(request, queryset, services.mark_admitted, "admitted", "already admitted")

    @admin.action(description="Decline application")
    def action_mark_rejected(self, request, queryset):
        self._run(
            request,
            queryset,
            services.mark_rejected,
            "declined",
            "already declined",
            messages.WARNING,
        )

    @admin.action(description="Transfer to the Visa Support desk")
    def action_transfer_to_visa_desk(self, request, queryset):
        self._run(
            request,
            queryset,
            services.transfer_to_visa_desk,
            "transferred to the Visa Support desk",
            "not admitted yet, or already transferred",
        )

    @admin.action(description="Email a message")
    def action_send_email_to_applicants(self, request, queryset):
        """Write to the owner of each file: the applicant, or the agent who filed it."""
        if request.POST.get("apply") == "send_email":
            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(
                    request, "Subject and message body are both required.", messages.ERROR
                )
                return None
            count = 0
            for app in queryset:
                services.send_applicant_email_message(app, subject, message_body)
                count += 1
            self.message_user(
                request,
                f"Message queued for {_plural(count, 'application')}. Files filed by an "
                "agent were written to the agent, not the student.",
                messages.SUCCESS,
            )
            return None

        return render(
            request,
            "admin/send_email_intermediate.html",
            {
                "title": "Email a message",
                "applicants": queryset,
            },
        )

    @admin.action(description="Resend login details (sets a new password)")
    def action_resend_login(self, request, queryset):
        """Email an applicant their sign-in details again.

        For the applicants whose credentials email never arrived. A fresh password
        is generated rather than reusing the old one, because the old one is not
        recoverable once it has been cleared, and because an email that may have
        gone astray is not a password worth keeping.

        Sent on this thread so the result is real: the count reported is what was
        delivered, not what was attempted.
        """
        from django.utils.crypto import get_random_string

        from apps.accounts.emails import send_applicant_welcome_email

        sent, failed, skipped = 0, [], []
        for application in queryset.select_related("applicant"):
            user = application.applicant
            if user is None or not user.email:
                skipped.append(application.reference)
                continue
            if application.submitted_by_agent is not None:
                # An agent-filed student is never written to: the agent owns that
                # relationship and holds no password for the student either.
                skipped.append(f"{application.reference} (agent-filed)")
                continue

            password = "Gabstep" + get_random_string(
                6, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            )
            user.set_password(password)
            user.save(update_fields=["password"])

            if send_applicant_welcome_email(user, password=password, wait=True):
                application.welcome_email_sent = True
                application.initial_password = ""
                application.save(update_fields=["welcome_email_sent", "initial_password"])
                sent += 1
            else:
                # The new password is already on the account, so it is kept here
                # for another attempt rather than being lost with the failed send.
                application.initial_password = password
                application.welcome_email_sent = False
                application.save(update_fields=["welcome_email_sent", "initial_password"])
                failed.append(application.reference)

        if sent:
            self.message_user(
                request,
                f"Login details emailed for {_plural(sent, 'application')}. "
                "Each one now has a new password; any earlier one no longer works.",
                messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                "Could not send for " + ", ".join(failed) + ". The mail provider "
                "refused or could not be reached. Run `manage.py mail_check` on the "
                "server to see why, then run this again.",
                messages.ERROR,
            )
        if skipped:
            self.message_user(
                request, "Skipped " + ", ".join(skipped) + ".", messages.WARNING
            )

    def save_formset(self, request, form, formset, change):
        """Stamp who issued a letter, and tell the applicant it has arrived."""
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            is_new_letter = isinstance(instance, Letter) and instance.pk is None
            if isinstance(instance, Letter) and instance.issued_by_id is None:
                instance.issued_by = request.user
            instance.save()
            if is_new_letter and instance.is_published:
                services.announce_letter(instance)

        formset.save_m2m()


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    """Letters on their own, for when you are issuing a batch of them."""

    list_display = ("title", "application", "kind", "published_badge", "issued_at", "issued_by")
    list_filter = ("kind", "is_published", "issued_at")
    search_fields = ("title", "application__reference", "application__full_name")
    autocomplete_fields = ("application",)
    date_hierarchy = "issued_at"
    readonly_fields = ("issued_by", "created_at", "download")
    actions = ("action_publish", "action_unpublish")

    fieldsets = (
        (None, {"fields": ("application", "kind", "title", "file", "download", "note")}),
        ("Publication", {"fields": ("is_published", "issued_at", "issued_by", "created_at")}),
    )

    @admin.display(description="Visible to applicant", boolean=True, ordering="is_published")
    def published_badge(self, obj):
        return obj.is_published

    @admin.display(description="Download")
    def download(self, obj):
        if not obj.file:
            return "None"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', obj.file.url, obj.filename
        )

    def save_model(self, request, obj, form, change):
        was_published = False
        if change:
            was_published = Letter.objects.filter(pk=obj.pk, is_published=True).exists()
        if obj.issued_by_id is None:
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)

        if obj.is_published and not was_published:
            services.announce_letter(obj)

    @admin.action(description="Publish to the applicant's dashboard")
    def action_publish(self, request, queryset):
        count = 0
        for letter in queryset.filter(is_published=False):
            letter.is_published = True
            letter.issued_at = letter.issued_at or timezone.now()
            letter.save(update_fields=["is_published", "issued_at"])
            services.announce_letter(letter)
            count += 1
        self.message_user(request, f"{_plural(count, 'letter')} published.", messages.SUCCESS)

    @admin.action(description="Unpublish (hide from the applicant)")
    def action_unpublish(self, request, queryset):
        count = queryset.update(is_published=False)
        self.message_user(request, f"{_plural(count, 'letter')} hidden.", messages.WARNING)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """The review desk: what applicants have uploaded, and whether it passes."""

    list_display = ("name", "application", "kind", "status_badge", "size", "uploaded_at", "download")
    list_filter = ("status", "kind", "uploaded_at")
    search_fields = ("name", "original_filename", "application__reference", "application__full_name")
    autocomplete_fields = ("application",)
    date_hierarchy = "uploaded_at"
    readonly_fields = ("size_bytes", "original_filename", "uploaded_at", "download")
    actions = ("action_verify", "action_reject")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return ApplicationAdmin._pill(
            obj.get_status_display(),
            {"Verified": "ok", "Rejected": "bad"}.get(obj.status, "wait"),
        )

    @admin.display(description="Size")
    def size(self, obj):
        return obj.human_size

    @admin.display(description="File")
    def download(self, obj):
        if not obj.file:
            return "None"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open</a>', obj.file.url
        )

    @admin.action(description="Verify selected documents")
    def action_verify(self, request, queryset):
        pending = list(queryset.exclude(status=Document.Status.VERIFIED))
        queryset.update(status=Document.Status.VERIFIED)
        for document in pending:
            services.notify(document.application, f"{document.name} has been verified.")
        self.message_user(
            request, f"{_plural(len(pending), 'document')} verified.", messages.SUCCESS
        )

    @admin.action(description="Reject selected documents (asks for a new copy)")
    def action_reject(self, request, queryset):
        pending = list(queryset.exclude(status=Document.Status.REJECTED))
        queryset.update(status=Document.Status.REJECTED)
        for document in pending:
            services.notify(
                document.application,
                f"{document.name} was not clear enough. Please upload a replacement from Details.",
            )
        self.message_user(
            request, f"{_plural(len(pending), 'document')} rejected.", messages.WARNING
        )


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    """Approving a correction writes it to the file where it is a plain value."""

    list_display = (
        "ticket",
        "application",
        "field",
        "current_value",
        "corrected_value",
        "status_badge",
        "created_at",
    )
    list_filter = ("status", "field", "created_at")
    search_fields = ("ticket", "application__reference", "application__full_name", "corrected_value")
    autocomplete_fields = ("application",)
    date_hierarchy = "created_at"
    readonly_fields = ("ticket", "created_at", "evidence_link")
    actions = ("action_approve", "action_decline")

    fieldsets = (
        (None, {"fields": ("ticket", "application", "field", "status")}),
        ("The change", {"fields": ("current_value", "corrected_value", "reason")}),
        ("Evidence", {"fields": ("evidence", "evidence_link", "created_at")}),
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return ApplicationAdmin._pill(
            obj.get_status_display(),
            {"verified": "ok", "declined": "bad"}.get(obj.status, "wait"),
        )

    @admin.display(description="Attached evidence")
    def evidence_link(self, obj):
        if not obj.evidence:
            return "None attached."
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open</a>', obj.evidence.url
        )

    @admin.action(description="Approve correction")
    def action_approve(self, request, queryset):
        approved = 0
        applied = 0
        for correction in queryset:
            changed, written = services.approve_correction(correction)
            approved += int(changed)
            applied += int(written)
        self.message_user(
            request,
            f"{_plural(approved, 'correction')} approved, {applied} written straight to the file."
            + (
                " The rest change a relation, so action them on the application itself."
                if approved > applied
                else ""
            ),
            messages.SUCCESS if approved else messages.INFO,
        )

    @admin.action(description="Decline correction")
    def action_decline(self, request, queryset):
        count = sum(1 for correction in queryset if services.decline_correction(correction))
        self.message_user(
            request, f"{_plural(count, 'correction')} declined.", messages.WARNING
        )


@admin.register(VisaSupportApplication)
class VisaSupportApplicationAdmin(admin.ModelAdmin):
    """Dedicated queue for admitted students & files transferred to Visa Support.

    Admissions and visa officers can track all student details, academic history,
    target institution, and attached offer/acceptance letters here.
    """

    list_display = (
        "reference",
        "full_name",
        "verification_badge",
        "destination_country",
        "institution",
        "visa_badge",
        "transfer_badge",
        "attached_letters_summary",
        "transferred_to_visa_support_at",
    )
    list_filter = (
        VerificationStatusFilter,
        "verification_status",
        "transferred_to_visa_support",
        "visa_status",
        "status",
        "destination_country",
        HasLetterFilter,
    )
    search_fields = (
        "reference",
        "full_name",
        "email",
        "phone",
        "institution__name",
    )
    autocomplete_fields = ("institution", "applicant")
    filter_horizontal = ("programs",)
    date_hierarchy = "submitted_at"
    list_per_page = 40
    save_on_top = True
    inlines = (LetterInline, DocumentInline, StageInline, NotificationInline)
    readonly_fields = (
        "reference",
        "submitted_at",
        "created_at",
        "updated_at",
        "transferred_to_visa_support_at",
        "payment_summary",
        "attached_letters_summary",
    )

    fieldsets = (
        (
            "Visa Support Status",
            {
                "fields": (
                    "reference",
                    ("transferred_to_visa_support", "transferred_to_visa_support_at"),
                    ("status", "visa_status"),
                    "attached_letters_summary",
                )
            },
        ),
        (
            "Applicant Details",
            {
                "fields": (
                    ("full_name", "email"),
                    ("phone", "address"),
                    ("origin_country", "destination_country"),
                    "applicant",
                    "submitted_by_agent",
                )
            },
        ),
        (
            "Academic Record",
            {
                "fields": (
                    "previous_schools",
                    ("qualification", "year_graduated", "grade_gpa"),
                )
            },
        ),
        ("Target Institution & Programme", {"fields": ("institution", "programs")}),
        (
            "Payment & Internal Notes",
            {
                "fields": (
                    "payment_summary",
                    "notes",
                    "submitted_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "action_start_visa_processing",
        "action_mark_visa_verified",
    )

    def get_queryset(self, request):
        # The queue is admitted students, and anyone who sent their letter to
        # the desk from their Letters page.
        return (
            super()
            .get_queryset(request)
            .filter(Q(status=Application.Status.ADMITTED) | Q(transferred_to_visa_support=True))
            .select_related("institution", "destination_country", "submitted_by_agent")
            .prefetch_related("stages", "letters")
            .annotate(letter_count=Count("letters", distinct=True))
        )

    @admin.display(description="Verification", ordering="verification_status")
    def verification_badge(self, obj):
        summary = obj.verification_summary
        status = summary["status"]
        cleared = summary["cleared_count"]
        total = summary["total_count"]

        if status == Application.VerificationStatus.VERIFIED:
            return ApplicationAdmin._pill("Verified ✓", "ok")
        if status == Application.VerificationStatus.IN_REVIEW:
            return ApplicationAdmin._pill(f"In Review ({cleared}/{total})", "info")
        if status == Application.VerificationStatus.ACTION_REQUIRED:
            return ApplicationAdmin._pill("Action Required", "bad")
        return ApplicationAdmin._pill(f"Unverified ({cleared}/{total})", "wait")

    @admin.display(description="Visa Status", ordering="visa_status")
    def visa_badge(self, obj):
        tone = {
            Application.VisaStatus.COMPLETED: "ok",
            Application.VisaStatus.IN_PROGRESS: "wait",
        }.get(obj.visa_status, "idle")
        return ApplicationAdmin._pill(obj.get_visa_status_display(), tone)

    @admin.display(description="Visa Desk Transfer", ordering="transferred_to_visa_support")
    def transfer_badge(self, obj):
        if obj.transferred_to_visa_support:
            return ApplicationAdmin._pill("Transferred to Desk", "ok")
        return ApplicationAdmin._pill("Not Transferred", "idle")

    @admin.display(description="Attached Letter(s)")
    def attached_letters_summary(self, obj):
        letters = list(obj.letters.all())
        if not letters:
            return format_html('<span style="color:#94a3b8">No letters issued yet</span>')
        links = []
        for let in letters:
            if let.file:
                links.append(
                    format_html(
                        '<a href="{}" target="_blank" rel="noopener" style="display:inline-block;padding:3px 8px;margin:2px 0;background:#eff6ff;color:#1d4ed8;border-radius:6px;font-weight:600;text-decoration:none;border:1px solid #bfdbfe;">📥 {} ({})</a>',
                        let.file.url,
                        let.title,
                        let.get_kind_display(),
                    )
                )
            else:
                links.append(format_html('<span>{}</span>', let.title))
        return format_html("<br>".join(links))

    @admin.display(description="Payment")
    def payment_summary(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "No payment recorded."
        link = reverse("admin:payments_payment_change", args=[payment.pk])
        return format_html(
            '{} · {} · <a href="{}">{}</a>',
            payment.display_total,
            payment.get_status_display(),
            link,
            payment.reference,
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            if "visa_status" in form.changed_data:
                services.notify(
                    obj, f"Your visa processing status was updated to: {obj.get_visa_status_display()}."
                )
            if "status" in form.changed_data:
                services.notify(
                    obj, f"Your application status was updated to: {obj.get_status_display()}."
                )

    @admin.action(description="Start visa processing")
    def action_start_visa_processing(self, request, queryset):
        changed = sum(1 for application in queryset if services.start_visa_processing(application))
        skipped = queryset.count() - changed
        if changed:
            self.message_user(
                request, f"{_plural(changed, 'application')} now in visa processing.", messages.SUCCESS
            )
        if skipped:
            self.message_user(
                request,
                f"{_plural(skipped, 'application')} skipped: visa work already started or finished.",
                messages.INFO,
            )

    @admin.action(description="Confirm visa approved (credits the agent's visa commission)")
    def action_mark_visa_verified(self, request, queryset):
        moved = 0
        paid = 0
        for application in queryset:
            changed, amount = services.mark_visa_verified(application)
            moved += int(changed)
            paid += amount
        skipped = queryset.count() - moved
        if moved:
            self.message_user(
                request,
                f"{_plural(moved, 'visa')} confirmed."
                + (f" ₦{paid:,.0f} commission credited to partner agents." if paid else ""),
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request, f"{_plural(skipped, 'application')} skipped: visa already confirmed.", messages.INFO
            )
