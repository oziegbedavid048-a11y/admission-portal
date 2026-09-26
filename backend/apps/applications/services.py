"""Actions that move an application forward.

Both the Django admin and the partner API need to advance a file, and they must
do it the same way: the same stages complete, the same notification reaches the
applicant, the same commission is paid once and only once. That logic lives here
so there is a single definition of what "admitted" means, rather than one in a
view and a second in an admin action that drift apart.

Every function here is safe to call twice. Re-running a milestone that has
already happened updates nothing and pays nothing.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.emails import _first_name, _url, send_async_email

from .constants import AGENT_COMMISSION_PER_MILESTONE, SUPERVISOR_BONUS_NGN
from .models import Application, Notification, Stage

# The stage each milestone leaves in progress once the ones before it are done.
STAGE_FOR_MILESTONE = {
    "documents": "Institution review",
    "admission": "Offer letter decision",
    "visa": "Visa guidance & enrolment",
}


def advance_stages_to(application, stage_name):
    """Complete every stage before ``stage_name`` and set that one in progress.

    A stage track is a sequence, so jumping to a later stage implies the earlier
    ones are finished; this keeps the applicant's ring and the agent's dossier
    telling the same story.
    """
    stages = list(application.stages.all())
    target = next((i for i, s in enumerate(stages) if s.name == stage_name), None)
    if target is None:
        return False

    for index, stage in enumerate(stages):
        if index < target:
            stage.status = Stage.Status.COMPLETED
        elif index == target:
            stage.status = Stage.Status.IN_PROGRESS
        else:
            stage.status = Stage.Status.PENDING
        stage.save(update_fields=["status"])
    return True


def complete_all_stages(application):
    """Close the file: every stage done, nothing left in progress."""
    application.stages.update(status=Stage.Status.COMPLETED)


def notify(application, text, send_email=True):
    """Write a line to the application's feed, and normally email it too.

    `send_email=False` is for the entries written while an application is being
    submitted: several land within a few seconds of each other, and mailing each
    one would mean half a dozen messages for a single action.
    """
    return Notification.objects.create(
        application=application, text=text, send_email=send_email
    )


def award_commission(application, kind):
    """Pay the agent for a milestone, once.

    Returns the amount credited, or zero if this application has no agent or the
    milestone was already paid. Imported lazily because ``partners`` reads its
    constants from this app, and a module-level import would close the loop.
    """
    from apps.partners.models import Commission

    agent = application.submitted_by_agent
    if agent is None:
        return 0

    _, created = Commission.objects.get_or_create(
        agent=agent,
        application=application,
        kind=kind,
        defaults={"amount": AGENT_COMMISSION_PER_MILESTONE},
    )
    if not created:
        return 0

    wallet = agent.wallet
    wallet.credit_commission(kind)

    if kind == Commission.Kind.REGISTRATION:
        agent.total_closed_sales = (agent.total_closed_sales or 0) + 1
        agent.save(update_fields=["total_closed_sales"])

    return AGENT_COMMISSION_PER_MILESTONE


def award_supervisor_bonus(application):
    """Pay the sales manager behind this student's agent, once.

    Earned at registration: a sales manager's job is recruiting and keeping
    agents productive, so the bonus follows the agent filing a student rather
    than anything that happens to that student later. Unique per application, so
    it is safe to call more than once. Returns the amount credited, or zero when
    the file has no agent, the agent has no supervisor, or it was already paid.
    """
    from apps.partners.models import SupervisorBonus

    agent = application.submitted_by_agent
    supervisor = getattr(agent, "supervisor", None) if agent else None
    if supervisor is None or not supervisor.is_active:
        return 0

    _, created = SupervisorBonus.objects.get_or_create(
        application=application,
        defaults={
            "supervisor": supervisor,
            "agent": agent,
            "amount": SUPERVISOR_BONUS_NGN,
        },
    )
    if not created:
        return 0

    supervisor.credit_bonus()
    return SUPERVISOR_BONUS_NGN


@transaction.atomic
def mark_documents_verified(application):
    """Every document checked; the file moves on to the institution."""
    changed = False
    if application.status != Application.Status.IN_REVIEW:
        application.status = Application.Status.IN_REVIEW
        application.save(update_fields=["status"])
        changed = True

    application.documents.update(status="Verified")
    advance_stages_to(application, STAGE_FOR_MILESTONE["documents"])

    if changed:
        notify(application, "Your documents are verified and your file is with the institution.")
    return changed


@transaction.atomic
def mark_admitted(application):
    """Admission granted. Advances the track; pays nothing.

    The agent was already paid when the fee settled, and is paid again when the
    visa is confirmed. Admission is a milestone the applicant cares about, not
    a billing event.
    """
    already = application.status == Application.Status.ADMITTED

    if not already:
        application.status = Application.Status.ADMITTED
        if application.visa_status == Application.VisaStatus.NOT_STARTED:
            application.visa_status = Application.VisaStatus.IN_PROGRESS
        application.save(update_fields=["status", "visa_status"])
        advance_stages_to(application, STAGE_FOR_MILESTONE["admission"])

        institution = application.institution.name if application.institution else "your institution"
        notify(application, f"Admission granted by {institution}. Your offer letter follows.")

    return not already, 0


@transaction.atomic
def mark_visa_verified(application):
    """Study permit confirmed. Closes the track and pays the agent."""
    already = application.visa_status == Application.VisaStatus.COMPLETED

    if not already:
        application.visa_status = Application.VisaStatus.COMPLETED
        if application.status != Application.Status.ADMITTED:
            application.status = Application.Status.ADMITTED
        application.save(update_fields=["status", "visa_status"])
        advance_stages_to(application, STAGE_FOR_MILESTONE["visa"])
        complete_all_stages(application)
        notify(application, "Your study permit is verified. Congratulations.")

    from apps.partners.models import Commission

    paid = award_commission(application, Commission.Kind.VISA)
    return not already, paid


@transaction.atomic
def mark_rejected(application, reason=""):
    """Decline the application and stop the track where it stands."""
    if application.status == Application.Status.REJECTED:
        return False

    application.status = Application.Status.REJECTED
    application.save(update_fields=["status"])
    application.stages.filter(status=Stage.Status.IN_PROGRESS).update(
        status=Stage.Status.PENDING
    )
    notify(
        application,
        reason or "Your application was not successful at this institution. An advisor will be in touch.",
    )
    return True


# Which application field each correction request writes to when approved.
CORRECTION_FIELDS = {
    "Legal name": "full_name",
    "full_name": "full_name",
    "Full Name": "full_name",
    "Name": "full_name",
    "Phone": "phone",
    "phone": "phone",
    "Phone number": "phone",
    "Address": "address",
    "address": "address",
    "Residential address": "address",
    "Email": "email",
    "email": "email",
    "Email address": "email",
    "Previous schools": "previous_schools",
    "previous_schools": "previous_schools",
    "Previous school": "previous_schools",
    "Qualification": "qualification",
    "qualification": "qualification",
    "Highest qualification": "qualification",
    "Year graduated": "year_graduated",
    "year_graduated": "year_graduated",
    "Grade or GPA": "grade_gpa",
    "grade_gpa": "grade_gpa",
    "Grade / GPA": "grade_gpa",
    "Destination country": "destination_country",
    "destination_country": "destination_country",
    "Institution": "institution",
    "institution": "institution",
    "University": "institution",
}


@transaction.atomic
def approve_correction(correction):
    """Accept a correction, applying it to the application file where valid."""
    from .models import CorrectionRequest, DestinationCountry, Institution, Program

    if correction.status == CorrectionRequest.Status.VERIFIED:
        return False, False

    correction.status = CorrectionRequest.Status.VERIFIED
    correction.save(update_fields=["status"])

    application = correction.application
    field_key = correction.field.strip()
    field = CORRECTION_FIELDS.get(field_key, CORRECTION_FIELDS.get(field_key.lower()))
    applied = False

    if field == "institution":
        inst = Institution.objects.filter(
            Q(name__iexact=correction.corrected_value)
            | Q(slug__iexact=correction.corrected_value)
        ).first()
        if inst:
            application.institution = inst
            application.save(update_fields=["institution"])
            applied = True
    elif field == "destination_country":
        country = DestinationCountry.objects.filter(
            name__iexact=correction.corrected_value
        ).first()
        if country:
            application.destination_country = country
            application.save(update_fields=["destination_country"])
            applied = True
    elif field_key.lower() in ("course", "program", "programme", "programs"):
        prog = Program.objects.filter(
            name__iexact=correction.corrected_value
        ).first()
        if prog:
            application.programs.clear()
            application.programs.add(prog)
            applied = True
    elif field and hasattr(application, field):
        val = correction.corrected_value
        if field == "year_graduated":
            try:
                val = int(val)
            except (ValueError, TypeError):
                val = None
        setattr(application, field, val)
        application.save(update_fields=[field])
        applied = True

        if field == "full_name":
            user = application.applicant
            user.full_name = correction.corrected_value
            user.save(update_fields=["full_name"])

    notify(
        application,
        f"Your correction to {correction.field} ({correction.ticket}) was approved and applied to your application file."
        if applied
        else f"Your correction to {correction.field} ({correction.ticket}) was approved and verified by the admissions desk.",
    )
    return True, applied


@transaction.atomic
def decline_correction(correction, reason=""):
    from .models import CorrectionRequest

    if correction.status == CorrectionRequest.Status.DECLINED:
        return False

    correction.status = CorrectionRequest.Status.DECLINED
    correction.save(update_fields=["status"])
    notify(
        correction.application,
        reason
        or f"Your correction to {correction.field.lower()} ({correction.ticket}) was not accepted. "
        "An advisor will explain why.",
    )
    return True


@transaction.atomic
def award_registration_commission(application):
    """Pay the agent for a student whose application fee has been settled.

    This is the only path that credits a registration commission, and it checks
    the payment itself rather than trusting the caller: a file with no payment,
    or one that is still pending or was waived, earns nothing. Called once from
    checkout and again from the admin when a fee is confirmed by hand, and safe
    both times because the commission is unique per application.
    """
    from apps.partners.models import Commission

    agent = application.submitted_by_agent
    if agent is None:
        return 0

    payment = getattr(application, "payment", None)
    from apps.payments.models import Payment

    if payment is None or payment.status != Payment.Status.PAID:
        return 0

    amount = award_commission(application, Commission.Kind.REGISTRATION)
    if amount:
        notify(
            application,
            f"Your education partner, {agent.user.full_name}, has settled your "
            "application fee.",
        )
    return amount


@transaction.atomic
def verify_application_full(application, verified_by=None, notes=""):
    """Verify all four audit checkpoints and mark the application fully verified."""
    application.personal_details_verified = True
    application.academic_details_verified = True
    application.documents_verified = True
    application.payment_verified = True
    application.verification_status = Application.VerificationStatus.VERIFIED
    application.verified_at = timezone.now()
    if verified_by:
        application.verified_by = verified_by
    if notes:
        application.verification_notes = notes

    application.save(
        update_fields=[
            "personal_details_verified",
            "academic_details_verified",
            "documents_verified",
            "payment_verified",
            "verification_status",
            "verified_at",
            "verified_by",
            "verification_notes",
            "updated_at",
        ]
    )

    # Also mark all uploaded documents as Verified
    application.documents.exclude(status="Verified").update(status="Verified")

    # If currently at document verification stage, advance it to institution review
    current = application.current_stage
    if current and current.name == "Document verification":
        advance_stages_to(application, STAGE_FOR_MILESTONE["documents"])

    notify(
        application,
        "Your application profile, documents, and credentials have been verified and approved by the admissions desk.",
    )

    # Dispatch confirmation email
    first_name = _first_name(application.full_name)
    subject = f"Application Details Verified · {application.reference}"
    text_content = (
        f"Hello {first_name},\n\n"
        f"Great news! Your application ({application.reference}) has been thoroughly reviewed and "
        "verified by the Gabstep admissions desk.\n\n"
        f"Institution: {application.institution.name if application.institution else 'Selected University'}\n"
        f"Destination: {application.destination_country.name if application.destination_country else ''}\n\n"
        "Your file is now proceeding to the next milestone. Log in to your portal anytime to view your progress:\n"
        f"{_url('/portal')}\n\n"
        "Best regards,\n"
        "Gabstep Admissions Desk"
    )
    html_content = (
        f"<p>Hello {first_name},</p>"
        f"<p>Great news! Your application <strong>{application.reference}</strong> has been thoroughly reviewed and "
        "verified by the Gabstep admissions desk.</p>"
        f"<p><strong>Institution:</strong> {application.institution.name if application.institution else 'Selected University'}<br>"
        f"<strong>Destination:</strong> {application.destination_country.name if application.destination_country else ''}</p>"
        f'<p><a href="{_url("/portal")}">Open Your Applicant Portal &rarr;</a></p>'
        "<p>Best regards,<br>Gabstep Admissions Desk</p>"
    )
    send_async_email(subject, text_content, html_content, [application.email])
    return True


@transaction.atomic
def set_verification_status(application, status, verified_by=None, notes=""):
    """Update verification status with corresponding notifications."""
    application.verification_status = status
    if status == Application.VerificationStatus.VERIFIED:
        application.personal_details_verified = True
        application.academic_details_verified = True
        application.documents_verified = True
        application.payment_verified = True
        application.verified_at = timezone.now()
        application.documents.exclude(status="Verified").update(status="Verified")
    elif status == Application.VerificationStatus.UNVERIFIED:
        application.personal_details_verified = False
        application.academic_details_verified = False
        application.documents_verified = False
        application.verified_at = None

    if verified_by:
        application.verified_by = verified_by
    if notes:
        application.verification_notes = notes

    application.save()

    status_labels = {
        Application.VerificationStatus.VERIFIED: "verified and approved",
        Application.VerificationStatus.IN_REVIEW: "placed under active review",
        Application.VerificationStatus.ACTION_REQUIRED: "flagged: action required",
        Application.VerificationStatus.UNVERIFIED: "queued for admissions verification",
    }
    label = status_labels.get(status, status)
    notify(application, f"Your application verification audit was updated: {label}.")
    return True


def send_applicant_email_message(application, subject, message_body, sender=None):
    """Send an arbitrary custom email or update note to the applicant from the admin."""
    first_name = _first_name(application.full_name)
    formatted_subject = f"{subject} · {application.reference}"
    text_content = (
        f"Hello {first_name},\n\n"
        f"{message_body}\n\n"
        f"Reference: {application.reference}\n"
        f"View your dashboard: {_url('/portal')}\n\n"
        "Best regards,\n"
        "Gabstep Admissions Desk"
    )
    html_content = (
        f"<p>Hello {first_name},</p>"
        f"<p>{message_body.replace(chr(10), '<br>')}</p>"
        f"<p><strong>Reference:</strong> {application.reference}</p>"
        f'<p><a href="{_url("/portal")}">Open Your Applicant Portal &rarr;</a></p>'
        "<p>Best regards,<br>Gabstep Admissions Desk</p>"
    )
    send_async_email(formatted_subject, text_content, html_content, [application.email])
    notify(application, f"Staff Message: {subject} — {message_body[:200]}")
    return True
