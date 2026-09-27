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

from .models import Payment

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

    fields = ["gateway", "status", "paid_at"]
    if gateway_reference and locked.gateway_reference != gateway_reference:
        locked.gateway_reference = gateway_reference
        fields.append("gateway_reference")

    locked.mark_paid(gateway_name or locked.gateway)
    if "gateway_reference" in fields:
        locked.save(update_fields=["gateway_reference"])

    services.notify(
        locked.application,
        f"Payment of {locked.display_total} confirmed. "
        "Your receipt is ready to download.",
    )

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
    app = locked.application
    if app and getattr(app, "initial_password", "") and not getattr(app, "welcome_email_sent", False):
        from apps.accounts.emails import send_applicant_welcome_email

        delivered = send_applicant_welcome_email(
            app.applicant, password=app.initial_password, wait=True
        )
        if delivered:
            app.welcome_email_sent = True
            app.initial_password = ""
            app.save(update_fields=["welcome_email_sent", "initial_password"])
            logger.info("Login details emailed to %s for %s", app.email, app.reference)
        else:
            # Left for a retry: the password stays, the flag stays down, and
            # "Resend login details" in the admin can pick it up.
            logger.error(
                "Could not email login details for %s to %s. The password is kept "
                "so it can be resent.",
                app.reference, app.email,
            )

    # A settled fee is what earns a partner agent their first commission. This is
    # the only place that happens, so it can only happen once.
    credited = services.award_registration_commission(locked.application)
    logger.info(
        "Payment %s settled via %s. Commission credited: %s",
        locked.reference,
        gateway_name or locked.gateway,
        credited,
    )
    # Keep the caller's instance in step with what was written.
    payment.refresh_from_db()
    return True
