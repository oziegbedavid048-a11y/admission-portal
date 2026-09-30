"""The application itself: one file per applicant, and everything hanging off it."""

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program

from .constants import DEFAULT_STAGES
from .uploads import correction_upload_path, document_upload_path, draft_upload_path, letter_upload_path


def generate_reference():
    """A human-quotable reference, e.g. APP-829143."""
    return f"APP-{secrets.randbelow(900000) + 100000}"


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "In review"
        ADMITTED = "admission_granted", "Admitted"
        REJECTED = "rejected", "Rejected"

    class VisaStatus(models.TextChoices):
        NOT_STARTED = "new", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Verified"

    class Qualification(models.TextChoices):
        SSCE = "SSCE / High School", "SSCE / High School"
        OND = "OND", "OND (Ordinary National Diploma)"
        HND = "HND", "HND (Higher National Diploma)"
        BACHELORS = "Bachelor's Degree", "Bachelor's Degree"
        MASTERS = "Master's Degree", "Master's Degree"

    reference = models.CharField(
        max_length=16, unique=True, default=generate_reference, editable=False
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    submitted_by_agent = models.ForeignKey(
        "partners.AgentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        help_text="Set when a partner agent filed this application for the student.",
    )

    # Step 1 — personal
    full_name = models.CharField(max_length=180)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=250, blank=True)
    origin_country = models.ForeignKey(
        OriginCountry, on_delete=models.PROTECT, related_name="applications"
    )
    destination_country = models.ForeignKey(
        DestinationCountry, on_delete=models.PROTECT, related_name="applications"
    )

    # Step 2 — academic
    previous_schools = models.CharField(max_length=250, blank=True)
    qualification = models.CharField(max_length=40, blank=True)
    year_graduated = models.PositiveSmallIntegerField(null=True, blank=True)
    grade_gpa = models.CharField(max_length=120, blank=True)

    # Step 3 — programme
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="applications",
        null=True,
        blank=True,
    )
    programs = models.ManyToManyField(Program, related_name="applications", blank=True)
    is_custom_course = models.BooleanField(
        default=False,
        help_text="True if applicant entered their desired course manually instead of picking from catalog.",
    )
    custom_course_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The course / program title typed directly by the applicant.",
    )

    # Pipeline
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.SUBMITTED
    )
    visa_status = models.CharField(
        max_length=16, choices=VisaStatus.choices, default=VisaStatus.NOT_STARTED
    )
    transferred_to_visa_support = models.BooleanField(
        default=False,
        help_text="Transferred to Visa Support Assistant for student visa processing.",
    )
    transferred_to_visa_support_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the file was transferred to Visa Support.",
    )
    initial_password = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Temporary password generated during application to be emailed upon successful payment settlement.",
    )
    welcome_email_sent = models.BooleanField(
        default=False,
        help_text="Whether the applicant welcome email with credentials has been dispatched.",
    )

    # Admissions Verification Audit
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        IN_REVIEW = "in_review", "In Review"
        VERIFIED = "verified", "Verified"
        ACTION_REQUIRED = "action_required", "Action Required"

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        help_text="Admissions desk verification and compliance status.",
    )
    personal_details_verified = models.BooleanField(
        default=False,
        help_text="Personal profile and contact info verified by admissions staff.",
    )
    academic_details_verified = models.BooleanField(
        default=False,
        help_text="Prior academic records, institution, and major choice verified.",
    )
    documents_verified = models.BooleanField(
        default=False,
        help_text="All submitted supporting documents verified by admissions staff.",
    )
    payment_verified = models.BooleanField(
        default=False,
        help_text="Application fee and tuition payment clearance confirmed.",
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when verification was completed.",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_applications",
        help_text="Staff member who conducted the verification audit.",
    )
    verification_notes = models.TextField(
        blank=True,
        help_text="Admissions desk remarks or instructions regarding applicant verification.",
    )

    notes = models.TextField(blank=True)

    submitted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-submitted_at",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("visa_status",)),
            models.Index(fields=("transferred_to_visa_support",)),
            models.Index(fields=("verification_status",)),
            models.Index(fields=["-submitted_at"], name="app_submitted_idx"),
            models.Index(fields=["email"], name="app_email_idx"),
            models.Index(fields=["submitted_by_agent", "-submitted_at"], name="app_agent_submitted_idx"),
        ]

    def __str__(self):
        return f"{self.reference} · {self.full_name}"

    @property
    def current_stage(self):
        """The stage in progress, or the last completed one if none is live."""
        stages = list(self.stages.all())
        if not stages:
            return None
        live = next((s for s in stages if s.status == Stage.Status.IN_PROGRESS), None)
        if live:
            return live
        done = [s for s in stages if s.status == Stage.Status.COMPLETED]
        return done[-1] if done else stages[0]

    @property
    def current_stage_index(self):
        stages = list(self.stages.all())
        current = self.current_stage
        return stages.index(current) if current in stages else 0

    @property
    def verification_summary(self):
        """Calculates verification completion score and checkpoint breakdown."""
        checkpoints = [
            # Two checks only. Personal and academic details are not verified:
            # a mistake there is fixed with a correction request instead.
            {
                "key": "payment",
                "label": "Application fee",
                "verified": bool(
                    self.payment_verified
                    or (
                        hasattr(self, "payment")
                        and getattr(self, "payment")
                        and getattr(self.payment, "status", "") in ("paid", "waived")
                    )
                ),
                "description": "Application fee paid and confirmed.",
            },
            {
                "key": "documents",
                "label": "Uploaded documents",
                "verified": bool(self.documents_verified),
                "description": "International passport data page, transcripts, and supporting documents verified.",
            },
        ]
        cleared_count = sum(1 for c in checkpoints if c["verified"])
        total_count = len(checkpoints)
        percentage = round((cleared_count / total_count) * 100) if total_count > 0 else 0

        status = self.verification_status
        if status == self.VerificationStatus.UNVERIFIED and cleared_count > 0:
            status = self.VerificationStatus.IN_REVIEW
        if cleared_count == total_count and status != self.VerificationStatus.ACTION_REQUIRED:
            status = self.VerificationStatus.VERIFIED

        return {
            "status": status,
            "status_display": dict(self.VerificationStatus.choices).get(status, status),
            "percentage": percentage,
            "cleared_count": cleared_count,
            "total_count": total_count,
            "is_fully_verified": status == self.VerificationStatus.VERIFIED or cleared_count == total_count,
            "verified_at": self.verified_at,
            "notes": self.verification_notes,
            "checkpoints": checkpoints,
        }

    def build_default_stages(self, first_note=""):
        """Lay down the five-stage track a new application starts with."""
        for order, spec in enumerate(DEFAULT_STAGES):
            if order == 0:
                status = Stage.Status.COMPLETED
            elif order == 1:
                status = Stage.Status.IN_PROGRESS
            else:
                status = Stage.Status.PENDING
            Stage.objects.create(
                application=self,
                order=order,
                name=spec["name"],
                note=first_note if order == 0 and first_note else spec["note"],
                eta=spec["eta"],
                status=status,
            )


class Stage(models.Model):
    """One step of the application timeline."""

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        IN_PROGRESS = "In Progress", "In progress"
        COMPLETED = "Completed", "Completed"

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="stages"
    )
    order = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=120)
    note = models.CharField(max_length=300, blank=True)
    eta = models.CharField(max_length=60, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order",)
        constraints = [
            models.UniqueConstraint(
                fields=("application", "order"), name="unique_stage_order"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


class Document(models.Model):
    """A credential on the applicant's file."""

    class Kind(models.TextChoices):
        PASSPORT = "passport", "International passport data page"
        ACADEMIC = "academic", "Academic documents & transcripts"
        CV = "cv", "Curriculum vitae / resume"
        OTHER = "other", "Supporting document"

    class Status(models.TextChoices):
        PENDING = "Pending Review", "Pending review"
        VERIFIED = "Verified", "Verified"
        REJECTED = "Rejected", "Rejected"

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    name = models.CharField(max_length=160)
    file = models.FileField(upload_to=document_upload_path, blank=True, null=True)
    original_filename = models.CharField(max_length=250, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    # Why a document was rejected, in the reviewer's words. Emailed to the
    # applicant and shown beside the document in their dashboard.
    review_note = models.TextField(blank=True, max_length=2000)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)
        indexes = [
            models.Index(fields=["application", "uploaded_at"], name="doc_app_uploaded_idx"),
            models.Index(fields=["status"], name="doc_status_idx"),
        ]
        verbose_name = "applicant document"
        verbose_name_plural = "applicant documents"

    def __str__(self):
        return f"{self.name} · {self.application.reference}"

    @property
    def human_size(self):
        size = self.size_bytes or 0
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"


class Notification(models.Model):
    """An entry in the applicant's activity feed."""

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="notifications"
    )
    text = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    send_email = models.BooleanField(
        default=True,
        help_text=(
            "Turned off for the entries written while an application is being "
            "submitted. Those all happen within a few seconds of the welcome "
            "email, and mailing each one would mean half a dozen messages for "
            "a single sign-up."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["application", "-created_at"], name="notif_app_created_idx"),
        ]

    def __str__(self):
        return self.text


class CorrectionRequest(models.Model):
    """A request to change a field that locked when the application was paid."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        VERIFIED = "verified", "Verified"
        DECLINED = "declined", "Declined"

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="corrections"
    )
    ticket = models.CharField(max_length=16, unique=True, editable=False)
    field = models.CharField(max_length=60)
    current_value = models.CharField(max_length=250, blank=True)
    corrected_value = models.CharField(max_length=250)
    reason = models.TextField()
    evidence = models.FileField(upload_to=correction_upload_path, blank=True, null=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"], name="corr_status_idx"),
        ]
        verbose_name = "correction request"
        verbose_name_plural = "correction requests"

    def __str__(self):
        return f"{self.ticket} · {self.field}"

    def save(self, *args, **kwargs):
        if not self.ticket:
            self.ticket = f"TK-{secrets.randbelow(9000) + 1000}"
        super().save(*args, **kwargs)


class ApplicationDraft(models.Model):
    """The wizard's saved progress, so an applicant can come back to it."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="draft"
    )
    current_step = models.PositiveSmallIntegerField(default=1)
    data = models.JSONField(default=dict)
    saved_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Draft for {self.user.email} (step {self.current_step})"


class ApplicationDraftFile(models.Model):
    """A document saved with an applicant's draft. Becomes a real document on submit."""

    draft = models.ForeignKey(ApplicationDraft, on_delete=models.CASCADE, related_name="files")
    # passport, academic, cv, or other-<n>.
    slot = models.CharField(max_length=24)
    kind = models.CharField(max_length=16, default="other")
    name = models.CharField(max_length=160)
    file = models.FileField(upload_to=draft_upload_path)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)
        constraints = [
            models.UniqueConstraint(fields=["draft", "slot"], name="one_file_per_application_draft_slot"),
        ]


class Letter(models.Model):
    """An official document the admissions desk issues TO the applicant.

    Documents flow the other way: the applicant uploads those. A letter is
    uploaded by staff and, once published, appears on the applicant's dashboard
    for them to download. Keeping it unpublished lets a letter be staged and
    checked before the applicant is told about it.
    """

    class Kind(models.TextChoices):
        OFFER = "offer", "Offer letter"
        ADMISSION = "admission", "Admission letter"
        ACCEPTANCE = "acceptance", "Confirmation of acceptance"
        VISA = "visa", "Visa / study permit"
        FINANCIAL = "financial", "Financial or scholarship letter"
        OTHER = "other", "Other correspondence"

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="letters"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OFFER)
    title = models.CharField(
        max_length=160, help_text="What the applicant sees, e.g. 'Conditional offer'."
    )
    file = models.FileField(upload_to=letter_upload_path)
    note = models.TextField(
        blank=True, help_text="Optional context shown beneath the title."
    )
    is_published = models.BooleanField(
        default=True,
        help_text="Unpublished letters are staged for review and stay hidden from the applicant.",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_letters",
    )
    issued_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-issued_at",)
        indexes = [
            models.Index(fields=["application", "is_published"], name="letter_app_published_idx"),
        ]
        verbose_name = "issued letter"
        verbose_name_plural = "issued letters"

    def __str__(self):
        return f"{self.title} · {self.application.reference}"

    @property
    def filename(self):
        return self.file.name.rsplit("/", 1)[-1] if self.file else ""


class VisaSupportApplication(Application):
    """Admitted student files transferred to the Visa Support Assistant desk.

    Provides admissions and visa officers with a focused workspace to track
    admitted applicants, review their issued acceptance letters, and progress their
    visa documentation.
    """

    class Meta:
        proxy = True
        verbose_name = "Visa Support Queue (Admitted Student)"
        verbose_name_plural = "Visa Support Queue (Admitted Students)"


# ── Signals ──────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Notification)
def send_notification_email_on_create(sender, instance, created, **kwargs):
    """Whenever a notification is created for an application, email the applicant."""
    if created and instance.send_email and not kwargs.get("raw", False):
        try:
            from apps.accounts.emails import send_application_status_update_email

            send_application_status_update_email(instance.application, instance.text)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Failed to dispatch notification email for %s: %s",
                instance.application.reference,
                exc,
            )



# ── Admin views over agent-filed files ─────────────────────────────────
# Proxies, so the admin can list agent-filed applications apart from the
# ones applicants made themselves, starting from the agent who filed them.

from apps.partners.models import AgentProfile  # noqa: E402


class AgentApplications(AgentProfile):
    """Every partner agent, as the way in to the students they registered."""

    class Meta:
        proxy = True
        app_label = "applications"
        verbose_name = "agent applications"
        verbose_name_plural = "agent applications"


class AgentApplication(Application):
    """One application filed by a partner agent."""

    class Meta:
        proxy = True
        verbose_name = "agent-filed application"
        verbose_name_plural = "agent-filed applications"
