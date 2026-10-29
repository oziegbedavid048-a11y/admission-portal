"""Settling a payment, in one place.

Three things can settle a payment: the webhook, the applicant returning from
Paystack, and the desk confirming a transfer. If each did its own settling they
would drift, and the one that drifted would either pay a commission twice or not
at all. They all call `settle` instead.

`settle` is safe to call twice. It takes the row lock, re-reads the status inside
it, and does nothing if the payment is already settled — which is what makes a
retried webhook, a refreshed return page and an impatient desk clicking twice all
harmless.
"""

import logging

from django.db import transaction

from apps.applications import services

from django.utils import timezone

from .models import Payment, PaymentCharge

logger = logging.getLogger(__name__)


@transaction.atomic
def settle(payment, gateway_name=None, gateway_reference=None):
    """Mark a payment paid and pay the commission it earns. Idempotent.

    Returns True if this call is the one that settled it, False if it was already
    settled. Callers use that to decide whether to say anything to anyone.
    """
    # Re-read under a lock. Two deliveries of the same webhook can arrive at once,
    # and without this both would pass the status check and both would credit.
    locked = Payment.objects.select_for_update().get(pk=payment.pk)

    if locked.status in {Payment.Status.PAID, Payment.Status.WAIVED}:
        return False

    # Which amount this money is for. Paystack's reference names the attempt
    # (and so the charge row opened for it); a transfer the desk confirms is the
    # receipt waiting for review. A payment from before charges were recorded
    # has no row and pays whatever is owed, as it always did.
    charge = _charge_to_apply(locked, gateway_name, gateway_reference)
    if charge is not None and charge.status == PaymentCharge.Status.PAID:
        return False  # this money was already counted
    amount = charge.amount_ngn if charge is not None else locked.balance_ngn
    now = timezone.now()
    if charge is None:
        charge = PaymentCharge(
            payment=locked,
            kind=PaymentCharge.Kind.FULL if locked.paid_ngn <= 0 else PaymentCharge.Kind.BALANCE,
            amount_ngn=amount,
            expected_ngn=amount,
            gateway=gateway_name or locked.gateway,
            gateway_reference=gateway_reference or "",
        )
    charge.status = PaymentCharge.Status.PAID
    charge.paid_at = now
    charge.save()

    if gateway_reference and locked.gateway_reference != gateway_reference:
        locked.gateway_reference = gateway_reference
    locked.paid_ngn = min(locked.amount_ngn, (locked.paid_ngn or 0) + amount)
    if locked.paid_ngn < locked.amount_ngn:
        return _part_paid(locked, gateway_name, amount, payment)

    locked.save(update_fields=["paid_ngn", "gateway_reference"])
    locked.mark_paid(gateway_name or locked.gateway)

    # An agent's student: the commission email tells the agent the payment is
    # confirmed, so this feed line is not emailed as well.
    services.notify(
        locked.application,
        f"Payment of {locked.display_total} confirmed. "
        "Your receipt is ready to download.",
        send_email=locked.application.submitted_by_agent_id is None,
    )
    services.sync_payment_checkpoint(locked.application)
    _sync_covered(locked.application)

    # The applicant was given a password when they applied, and it is held back
    # until the fee is settled. Send it now.
    #
    # Sent on this thread, and the flag is only set once the send has actually
    # succeeded. The previous version queued it on a daemon thread, which cannot
    # report a failure, and then immediately recorded it as sent and cleared the
    # password. A send that failed therefore looked exactly like one that worked,
    # and the password was gone: the applicant could not be told their login and
    # nobody could recover it. Keeping the password until the mail is away is what
    # makes a retry, or a resend from the admin, possible at all.
    _send_login_once(locked.application)

    # A settled fee is what earns a partner agent their first commission. This is
    # the only place that happens, so it can only happen once.
    credited = services.award_registration_commission(locked.application)
    # The same paid fee earns the sales manager behind the agent their bonus.
    bonus = services.award_supervisor_bonus(locked.application)
    logger.info(
        "Payment %s settled via %s. Commission credited: %s. Manager bonus: %s",
        locked.reference,
        gateway_name or locked.gateway,
        credited,
        bonus,
    )
    # Keep the caller's instance in step with what was written.
    payment.refresh_from_db()
    return True


def _charge_to_apply(locked, gateway_name, gateway_reference):
    """The recorded charge this money settles, locked, or None."""
    rows = PaymentCharge.objects.select_for_update().filter(payment=locked)
    if gateway_reference:
        return rows.filter(gateway_reference=gateway_reference).first()
    if gateway_name == Payment.Gateway.TRANSFER:
        return rows.filter(status=PaymentCharge.Status.REVIEW).order_by("-created_at", "-pk").first()
    return None


def _part_paid(locked, gateway_name, amount, payment):
    """A deposit or an instalment is in, and more is still owed.

    The file counts as paid for the work to start (its fee check is ticked), and
    the login held back until payment is sent now. The agent's commission and
    the manager's bonus wait for the last payment: they are only paid on a fee
    that is Paid in full.
    """
    from . import plans

    first = locked.deposit_paid_at is None
    locked.status = Payment.Status.PART_PAID
    if gateway_name:
        locked.gateway = gateway_name
    if first:
        locked.deposit_paid_at = timezone.now()
    locked.review_note = ""
    locked.save(update_fields=["status", "gateway", "paid_ngn", "deposit_paid_at", "gateway_reference", "review_note"])

    upcoming = plans.next_instalment(locked)
    when = f", due {upcoming['due_on']:%d %b %Y}" if upcoming and upcoming["due_on"] else ""
    services.notify(
        locked.application,
        f"Payment of ₦{amount:,.0f} received. ₦{locked.balance_ngn:,.0f} of the application fee "
        f"is left to pay{when}. Work on your application has started.",
        # Emailed to whoever owns the file (the agent for a student they
        # filed): no commission email follows a part payment to tell them.
        send_email=True,
    )
    services.sync_payment_checkpoint(locked.application)
    _sync_covered(locked.application)
    if first:
        _send_login_once(locked.application)
    logger.info("Payment %s part paid: %s of %s.", locked.reference, locked.paid_ngn, locked.amount_ngn)
    payment.refresh_from_db()
    return True


def _sync_covered(primary):
    """The 2nd and 3rd choice files follow the 1st choice's fee."""
    for covered in primary.covered_applications.all():
        services.sync_payment_checkpoint(covered)


def _send_login_once(app):
    """Send the applicant's login, held back until payment, once.

    Sent on this thread, and the flag is only set once the send has actually
    succeeded, so a failed send can be retried and the password is never lost.
    """
    if not (app and getattr(app, "initial_password", "") and not getattr(app, "welcome_email_sent", False)):
        return
    from apps.accounts.emails import send_applicant_welcome_email

    delivered = send_applicant_welcome_email(app.applicant, password=app.initial_password, wait=True)
    if delivered:
        app.welcome_email_sent = True
        app.initial_password = ""
        app.save(update_fields=["welcome_email_sent", "initial_password"])
        logger.info("Login details emailed to %s for %s", app.email, app.reference)
    else:
        # Left for a retry: the password stays, the flag stays down, and
        # "Resend login details" in the admin can pick it up.
        logger.error(
            "Could not email login details for %s to %s. The password is kept so it can be resent.",
            app.reference, app.email,
        )
