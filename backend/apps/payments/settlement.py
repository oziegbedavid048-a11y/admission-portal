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
