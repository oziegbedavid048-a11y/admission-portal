"""What the applicant is charged, and why it is that number.

One rule: **the total shown is the total debited.** The quote used to add a flat
3.50 "processing fee" in whatever currency the applicant was quoted in, and then
ask the gateway for the application fee alone. Nobody was ever charged that 3.50,
so every receipt was wrong by it and the books would not have reconciled against
a settlement report.

So the processing fee is computed in Naira, from Paystack's published pricing,
added to the Naira amount the gateway is asked for, and only then converted for
display. The formula is theirs, not an invention:

    1.5% of the amount, plus a flat fee,
    the flat part waived below a threshold,
    the whole fee capped.

Every number is a setting, because a negotiated rate is normal.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from apps.applications import constants

KOBO = Decimal("0.01")


def _setting(name, fallback):
    return Decimal(str(getattr(settings, name, fallback)))


def processing_fee_ngn(amount_ngn):
    """Paystack's cut on this amount, in Naira, rounded to the kobo."""
    amount = Decimal(amount_ngn or 0)
    if amount <= 0:
        return Decimal("0.00")

    percent = _setting("PAYSTACK_FEE_PERCENT", constants.PAYSTACK_FEE_PERCENT)
    flat = _setting("PAYSTACK_FEE_FLAT_NGN", constants.PAYSTACK_FEE_FLAT_NGN)
    waived_under = _setting(
        "PAYSTACK_FEE_FLAT_WAIVED_UNDER_NGN", constants.PAYSTACK_FEE_FLAT_WAIVED_UNDER_NGN
    )
    cap = _setting("PAYSTACK_FEE_CAP_NGN", constants.PAYSTACK_FEE_CAP_NGN)

    fee = amount * percent / Decimal("100")
    if amount >= waived_under:
        fee += flat
    if cap > 0:
        fee = min(fee, cap)

    return fee.quantize(KOBO, rounding=ROUND_HALF_UP)


def minor_units(amount_ngn):
    """Naira as an integer of kobo, which is what Paystack counts in.

    Rounded up, never down: asking for a kobo less than the total would settle a
    payment for less than the quote and the webhook would refuse it.
    """
    amount = Decimal(amount_ngn or 0)
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
