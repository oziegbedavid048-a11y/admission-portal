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
from django.db.models import Q
from django.utils import timezone


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


# ── Verification checkpoints ─────────────────────────────────────────
# Four separate checks, one per part of the file. Each admin action ticks exactly
# one of them. The overall verification status is never set by hand: it follows
# from the checks, so it cannot disagree with them.

CHECKPOINTS = {
    "personal": ("personal_details_verified", "Your personal details have"),
    "academic": ("academic_details_verified", "Your academic details have"),
    "documents": ("documents_verified", "Your uploaded documents have"),
    "payment": ("payment_verified", "Your application fee has"),
}


def _refresh_verification_status(application, verified_by=None):
    """Recompute the overall status from the four checks. Does not save.

    Action required is left alone until a check changes, because it is a flag
    the desk raised on purpose, not something the checks can clear by themselves.
    """
    checks = [getattr(application, field) for field, _ in CHECKPOINTS.values()]
    if all(checks):
        application.verification_status = Application.VerificationStatus.VERIFIED
        application.verified_at = application.verified_at or timezone.now()
        if verified_by:
            application.verified_by = verified_by
    elif any(checks):
        application.verification_status = Application.VerificationStatus.IN_REVIEW
        application.verified_at = None
    else:
        application.verification_status = Application.VerificationStatus.UNVERIFIED
        application.verified_at = None


@transaction.atomic
def verify_checkpoint(application, checkpoint, verified_by=None):
    """Mark one of the four checks as passed. Returns False if it already was.

    For "documents" every uploaded file on the application is also marked
    Verified, because that check is the uploads: ticking it while the files still
    read Pending would show the applicant two different answers.
    """
    field, label = CHECKPOINTS[checkpoint]
    if getattr(application, field):
        return False

    setattr(application, field, True)
    was_verified = application.verification_status == Application.VerificationStatus.VERIFIED
    _refresh_verification_status(application, verified_by)
    application.save(
        update_fields=[field, "verification_status", "verified_at", "verified_by", "updated_at"]
    )
    if checkpoint == "documents":
        application.documents.exclude(status="Verified").update(status="Verified")

    if application.verification_status == Application.VerificationStatus.VERIFIED and not was_verified:
        notify(application, "Your application has been fully verified by the admissions desk.")
    else:
        notify(application, f"{label} been verified.")
    return True


@transaction.atomic
def flag_action_required(application, verified_by=None):
    """Tell the applicant something on the file needs their attention."""
    if application.verification_status == Application.VerificationStatus.ACTION_REQUIRED:
        return False
    application.verification_status = Application.VerificationStatus.ACTION_REQUIRED
    if verified_by:
        application.verified_by = verified_by
    application.save(update_fields=["verification_status", "verified_by", "updated_at"])
    notify(
        application,
        "The admissions desk needs something from you before your application can "
        "continue. An advisor will be in touch.",
    )
    return True


@transaction.atomic
def reset_verification(application):
    """Clear all four checks so the file is verified again from the start."""
    fields = [field for field, _ in CHECKPOINTS.values()]
    if not any(getattr(application, f) for f in fields) and (
        application.verification_status == Application.VerificationStatus.UNVERIFIED
    ):
        return False
    for field in fields:
        setattr(application, field, False)
    _refresh_verification_status(application)
    application.save(update_fields=[*fields, "verification_status", "verified_at", "updated_at"])
    notify(application, "Your application is back in the queue for verification.")
    return True


# ── Pipeline milestones ──────────────────────────────────────────────


@transaction.atomic
def send_to_institution(application):
    """Move a file whose uploads are verified on to the institution.

    Returns False when nothing moved: the file is already there or further on,
    or its uploaded documents have not been verified yet.
    """
    if not application.documents_verified:
        return False
    if application.status in (
        Application.Status.IN_REVIEW,
        Application.Status.ADMITTED,
        Application.Status.REJECTED,
    ):
        return False

    application.status = Application.Status.IN_REVIEW
    application.save(update_fields=["status", "updated_at"])
    advance_stages_to(application, STAGE_FOR_MILESTONE["documents"])
    notify(application, "Your file has been sent to the institution for review.")
    return True


@transaction.atomic
def mark_admitted(application):
    """Admission granted. Advances the track; pays nothing.

    The agent was already paid when the fee settled, and is paid again when the
    visa is confirmed. Admission is a milestone the applicant cares about, not
    a billing event.
    """
    if application.status == Application.Status.ADMITTED:
        return False

    application.status = Application.Status.ADMITTED
    application.save(update_fields=["status", "updated_at"])
    advance_stages_to(application, STAGE_FOR_MILESTONE["admission"])

    institution = application.institution.name if application.institution else "your institution"
    notify(application, f"Admission granted by {institution}. Your offer letter follows.")
    return True


@transaction.atomic
def transfer_to_visa_desk(application):
    """Hand an admitted file to the Visa Support desk. Only admitted files move."""
    if application.status != Application.Status.ADMITTED or application.transferred_to_visa_support:
        return False
    application.transferred_to_visa_support = True
    application.transferred_to_visa_support_at = timezone.now()
    application.save(
        update_fields=["transferred_to_visa_support", "transferred_to_visa_support_at", "updated_at"]
    )
    notify(application, "Your file has been passed to our Visa Support desk.")
    return True


@transaction.atomic
def start_visa_processing(application):
    """The visa desk has started work on an admitted file."""
    if application.status != Application.Status.ADMITTED:
        return False
    if application.visa_status != Application.VisaStatus.NOT_STARTED:
        return False
    application.visa_status = Application.VisaStatus.IN_PROGRESS
    application.save(update_fields=["visa_status", "updated_at"])
    advance_stages_to(application, STAGE_FOR_MILESTONE["visa"])
    notify(application, "Work on your visa application has started.")
    return True


@transaction.atomic
def mark_visa_verified(application):
    """Study permit confirmed. Closes the track and credits the agent's visa commission.

    The commission belongs to this milestone rather than a separate step: it is
    what the agent is owed for it, and a separate button is one that could be
    forgotten. Only admitted files qualify. Returns (changed, amount paid).
    """
    if application.status != Application.Status.ADMITTED:
        return False, 0
    if application.visa_status == Application.VisaStatus.COMPLETED:
        return False, 0

    application.visa_status = Application.VisaStatus.COMPLETED
    application.save(update_fields=["visa_status", "updated_at"])
    complete_all_stages(application)
    notify(application, "Your study permit is verified. Congratulations.")

    from apps.partners.models import Commission

    paid = award_commission(application, Commission.Kind.VISA)
    return True, paid


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


def send_applicant_email_message(application, subject, message_body):
    """Send a message the desk wrote to whoever owns this file.

    It lands on the application's feed and goes out by email once. A file an
    agent filed is written to the agent, never the student, exactly as every
    status update is.
    """
    from apps.accounts.emails import send_application_status_update_email

    notify(application, f"Message from the admissions desk: {subject}. {message_body}", send_email=False)
    send_application_status_update_email(application, message_body, subject_override=subject)
    return True


def announce_letter(letter):
    """A letter was published: one feed entry and one detailed email.

    The feed entry is written without its own email, because the letter email
    below carries the full news and a second, generic update would repeat it.
    """
    from apps.accounts.emails import send_letter_issued_email

    notify(
        letter.application,
        f"{letter.title} is ready. Open it from Letters in your dashboard.",
        send_email=False,
    )
    transaction.on_commit(lambda: send_letter_issued_email(letter))
