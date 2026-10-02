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


from .constants import AGENT_COMMISSION_BY_KIND, SUPERVISOR_BONUS_NGN
from .models import Application, Letter, Notification, Stage

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

    amount = AGENT_COMMISSION_BY_KIND[kind]
    _, created = Commission.objects.get_or_create(
        agent=agent,
        application=application,
        kind=kind,
        defaults={"amount": amount},
    )
    if not created:
        return 0

    # An agent added from the admin may not have a wallet yet; one is made
    # rather than losing the commission.
    from apps.partners.models import Wallet

    wallet, _ = Wallet.objects.get_or_create(agent=agent)
    wallet.credit_commission(kind, amount)

    if kind == Commission.Kind.REGISTRATION:
        agent.total_closed_sales = (agent.total_closed_sales or 0) + 1
        agent.save(update_fields=["total_closed_sales"])

    # Every naira that lands in the wallet is emailed to the agent.
    from apps.accounts.emails import send_commission_credited_email

    transaction.on_commit(
        lambda: send_commission_credited_email(agent, application, kind, amount)
    )
    return amount


def award_supervisor_bonus(application):
    """Pay the sales manager behind this student's agent, once.

    Earned when the student's application fee is paid. It used to be paid the
    moment an agent registered a student, so registering made-up students
    earned real money with no fee ever paid. Like the agent's registration
    commission, it checks the payment itself rather than trusting the caller,
    and it is unique per application, so it is safe to call more than once.
    Returns the amount credited, or zero when the fee is not paid, the file has
    no agent, the agent has no supervisor, or it was already paid.
    """
    from apps.partners.models import SupervisorBonus
    from apps.payments.models import Payment

    payment = getattr(application, "payment", None)
    if payment is None or payment.status != Payment.Status.PAID:
        return 0

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
# Two checks: the application fee and the uploaded documents. Neither is ticked
# by hand. The fee check follows the payment (Paystack, a confirmed transfer or
# a waiver) and the documents check follows the document review, so the
# overall status can never disagree with what actually happened. Personal and
# academic details are not verified; mistakes there go through corrections.

CHECKPOINTS = {
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


def sync_payment_checkpoint(application):
    """Tick the fee check once the fee is paid or waived. Never by hand."""
    payment = getattr(application, "payment", None)
    settled = bool(payment and payment.status in ("paid", "waived"))
    if application.payment_verified == settled:
        return
    application.payment_verified = settled
    _refresh_verification_status(application)
    application.save(
        update_fields=["payment_verified", "verification_status", "verified_at", "verified_by", "updated_at"]
    )


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


# ── Pipeline milestones ──────────────────────────────────────────────


# A student counts as admitted once the desk marks the file admitted, or as soon
# as an admission or offer letter for it is published, whichever comes first.
# Sending the letter is how the desk usually records the admission, so every
# "admitted" figure (agent overview, sales-manager overview and tables) follows
# this one rule rather than each keeping its own.
ADMISSION_LETTER_KINDS = (Letter.Kind.ADMISSION, Letter.Kind.OFFER)


def admitted_application_ids(application_ids):
    """The ids, out of the ones given, that count as admitted."""
    ids = list(application_ids)
    lettered = set(
        Letter.objects.filter(
            application__in=ids,
            is_published=True,
            kind__in=ADMISSION_LETTER_KINDS,
        ).values_list("application_id", flat=True)
    )
    marked = set(
        Application.objects.filter(pk__in=ids, status=Application.Status.ADMITTED).values_list(
            "pk", flat=True
        )
    )
    return lettered | marked


def reads_as_admitted(application):
    """Whether this application counts as admitted, from letters already loaded
    with it (prefetch "letters") so a table of students costs no extra queries."""
    if application.status == Application.Status.ADMITTED:
        return True
    return any(
        letter.is_published and letter.kind in ADMISSION_LETTER_KINDS
        for letter in application.letters.all()
    )


def admitted_q(prefix=""):
    """The same rule as a query filter. `prefix` reaches the application from
    another model, e.g. "applications__" from an agent."""
    return Q(**{f"{prefix}status": Application.Status.ADMITTED}) | Q(
        **{
            f"{prefix}letters__is_published": True,
            f"{prefix}letters__kind__in": ADMISSION_LETTER_KINDS,
        }
    )


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
def start_visa_processing(application):
    """The visa desk has started work on a file it holds."""
    if not in_visa_queue(application):
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
    """Visa support done. Closes the track and credits the agent's ₦50,000 visa commission.

    Sending a letter to visa support earns nothing by itself; this confirmation
    from the desk is what pays. It covers any file in the visa queue: admitted,
    or sent to visa support from a letter. Returns (changed, amount paid).
    """
    if not in_visa_queue(application):
        return False, 0
    if application.visa_status == Application.VisaStatus.COMPLETED:
        return False, 0

    application.visa_status = Application.VisaStatus.COMPLETED
    application.save(update_fields=["visa_status", "updated_at"])
    complete_all_stages(application)

    from apps.partners.models import Commission

    paid = award_commission(application, Commission.Kind.VISA)
    # For an agent's student the commission email already says the visa support
    # is done, so the feed entry is not emailed a second time.
    notify(
        application,
        "Visa support is complete. Your study permit is verified. Congratulations.",
        send_email=not paid,
    )
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
            f"Application fee settled by {agent.user.full_name}.",
            send_email=False,
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


# ── Document review ──────────────────────────────────────────────────
# Documents are reviewed one by one on the Documents screen. The application's
# "uploaded documents" check follows from them: it is ticked when every
# document on the file is verified, and unticked when one is rejected or
# replaced. It is never ticked by hand.


def sync_documents_checkpoint(application, reviewed_by=None):
    docs = list(application.documents.values_list("status", flat=True))
    all_verified = bool(docs) and all(status == "Verified" for status in docs)
    if application.documents_verified == all_verified:
        return
    application.documents_verified = all_verified
    _refresh_verification_status(application, reviewed_by)
    application.save(
        update_fields=["documents_verified", "verification_status", "verified_at", "verified_by", "updated_at"]
    )


@transaction.atomic
def verify_documents(documents, reviewed_by=None):
    """Mark documents verified. One notice per application, naming them all.

    The feed gets a line each time, but the email goes out once: when the last
    document on the file is verified, saying the whole set is accepted.
    """
    from collections import defaultdict

    from apps.accounts.emails import send_documents_verified_email

    changed = defaultdict(list)
    for document in documents:
        if document.status == "Verified":
            continue
        document.status = "Verified"
        document.review_note = ""
        document.reviewed_at = timezone.now()
        document.reviewed_by = reviewed_by
        document.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by"])
        changed[document.application_id].append(document)

    for docs in changed.values():
        application = docs[0].application
        names = ", ".join(doc.name for doc in docs)
        was_complete = application.documents_verified
        notify(application, f"Verified: {names}.", send_email=False)
        sync_documents_checkpoint(application, reviewed_by)
        if application.documents_verified and not was_complete:
            transaction.on_commit(lambda app=application: send_documents_verified_email(app))
    return sum(len(docs) for docs in changed.values())


@transaction.atomic
def reject_document(document, note, reviewed_by=None):
    """Reject one document with the reviewer's reason, and email that reason."""
    from apps.accounts.emails import send_document_rejected_email

    note = (note or "").strip()
    document.status = "Rejected"
    document.review_note = note
    document.reviewed_at = timezone.now()
    document.reviewed_by = reviewed_by
    document.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by"])

    application = document.application
    notify(application, f"{document.name} needs replacing: {note}", send_email=False)
    sync_documents_checkpoint(application, reviewed_by)
    transaction.on_commit(lambda: send_document_rejected_email(document))
    return True



@transaction.atomic
def reject_transfer(payment, note):
    """Turn down a transfer receipt with a reason. The payer can send another."""
    from apps.accounts.emails import send_transfer_rejected_email

    payment.status = "pending"
    payment.review_note = (note or "").strip()
    payment.save(update_fields=["status", "review_note"])
    notify(
        payment.application,
        f"Bank transfer not confirmed: {payment.review_note}",
        send_email=False,
    )
    transaction.on_commit(lambda: send_transfer_rejected_email(payment))
    return True



def in_visa_queue(application):
    """Whether the visa desk holds this file: admitted, or sent to visa support."""
    return (
        application.status == Application.Status.ADMITTED
        or bool(application.transferred_to_visa_support)
    )
