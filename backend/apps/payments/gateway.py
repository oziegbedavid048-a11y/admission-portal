"""Talking to the payment provider, and being told when money arrives.

The rule this module exists to enforce: **a payment is only settled by something
that can prove money moved.** Before this, the checkout endpoint settled the
payment itself. Anyone who could call it — including an agent, on a file they had
just created for a student — got the fee marked paid and the ₦30,000 registration
commission credited, without a naira arriving anywhere.

So settlement now has exactly two doors, and neither of them is the applicant's
browser:

  * a provider webhook whose signature verifies against the secret key, and
    whose amount matches what was quoted, or
  * the admissions desk confirming in the admin that a bank transfer landed.

`initiate` is what the browser gets: a pending payment and, when a provider is
configured, the URL to go and pay at. It never changes a status.

Paystack is the provider wired here because it is what the quote is denominated
against. It is active only when PAYSTACK_SECRET_KEY is set; with no key the
platform runs in transfer mode, which is a real way to take money, not a
simulation: the applicant transfers and the desk confirms.
"""

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)

PAYSTACK_API = "https://api.paystack.co"


def is_live():
    """Whether a provider is configured to collect money online."""
    return bool(getattr(settings, "PAYSTACK_SECRET_KEY", ""))


def _post(path, payload):
    body = json.dumps(payload).encode()
    req = request.Request(
        f"{PAYSTACK_API}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def initiate(payment, email, callback_url):
    """Ask the provider for somewhere to send the applicant to pay.

    Returns the URL to redirect to, or None when no provider is configured. The
    payment's status is not touched either way: it stays pending until something
    proves otherwise.
    """
    if not is_live():
        return None

    try:
        data = _post(
            "/transaction/initialize",
            {
                # Paystack counts in the minor unit, so kobo rather than naira.
                "amount": int((payment.amount_ngn * 100).to_integral_value()),
                "email": email,
                "currency": "NGN",
                "reference": payment.reference,
                "callback_url": callback_url,
                "metadata": {"application": payment.application.reference},
            },
        )
    except (error.URLError, error.HTTPError, ValueError, TimeoutError) as exc:
        # A provider that cannot be reached must not block the application from
        # being filed. The file stays submitted with the fee outstanding, and the
        # applicant can pay by transfer.
        logger.error("Could not initialise payment %s: %s", payment.reference, exc)
        return None

    if not data.get("status"):
        logger.error("Provider refused payment %s: %s", payment.reference, data.get("message"))
        return None

    return (data.get("data") or {}).get("authorization_url")


def signature_is_valid(raw_body, header_signature):
    """Whether this webhook really came from the provider.

    Paystack signs the raw request body with HMAC-SHA512 under the secret key.
    Without checking it, the webhook endpoint is a public "mark this paid" button,
    which is worse than the hole it was added to close. Compared in constant time
    so the check cannot be probed a byte at a time.
    """
    if not is_live() or not header_signature:
        return False
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, header_signature)


def amount_matches(payment, minor_units):
    """Whether the provider charged what we quoted.

    A signature proves the message came from the provider. It does not prove the
    amount: someone who can start a ₦100 charge against a known reference would
    otherwise have a ₦200,000 application fee settled for ₦100.
    """
    if minor_units is None:
        return False
    try:
        paid = (Decimal(minor_units) / 100).quantize(Decimal("0.01"))
    except (TypeError, ValueError, ArithmeticError):
        return False
    return paid >= payment.amount_ngn
