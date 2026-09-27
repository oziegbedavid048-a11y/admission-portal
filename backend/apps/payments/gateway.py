"""Talking to Paystack, and being told when money arrives.

The rule this module exists to enforce: **a payment is only settled by something
that can prove money moved.** The checkout endpoint used to settle the payment
itself, so anyone who could call it — including an agent, on a file they had just
created for a student — got the fee marked paid and the registration commission
credited, with no naira arriving anywhere.

Settlement now has exactly three doors, and none of them is the applicant's
browser:

  * `charge.success` on the webhook, where the signature verifies against the
    secret key and the amount matches the quote,
  * a server-to-server verify of the reference when the applicant returns from
    Paystack, which covers a webhook that is late or lost,
  * the admissions desk confirming in the admin that a bank transfer landed.

The browser's only role is to be sent somewhere and to come back with a reference
that this server then checks for itself.

Live when `PAYSTACK_SECRET_KEY` is set. The same variable holds a `sk_test_` or an
`sk_live_` key; Paystack decides which environment that is, so there is no mode
flag here to get out of step with the key. With no key the platform runs in
transfer mode, which is a real way to take money: the applicant transfers and the
desk confirms.
"""

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib import error, parse, request

from django.conf import settings

from .fees import minor_units

logger = logging.getLogger(__name__)

PAYSTACK_API = "https://api.paystack.co"
TIMEOUT = 20

# Paystack posts webhooks from these addresses. Checking them is defence in depth
# behind the signature, not instead of it: a proxy can rewrite the client address,
# and the signature is what actually proves the message. Off unless an allowlist
# is configured, because a platform that terminates TLS for you may not pass the
# real address through at all.
DEFAULT_WEBHOOK_IPS = ("52.31.139.75", "52.49.173.169", "52.214.14.220")


def is_live():
    """Whether a provider is configured to collect money online."""
    return bool(getattr(settings, "PAYSTACK_SECRET_KEY", ""))


def _call(path, payload=None, method="GET"):
    """One request to Paystack. Raises on anything that is not a clean answer."""
    body = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(
        f"{PAYSTACK_API}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    with request.urlopen(req, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode())


def initiate(payment, email, callback_url):
    """Ask Paystack for somewhere to send the applicant to pay.

    Returns the URL to redirect to, or None when there is no provider or the call
    failed. The payment's status is never touched: it stays pending until
    something proves otherwise.

    A fresh gateway reference is minted per attempt, because Paystack refuses a
    reference it has already seen. Without that, an applicant who abandoned the
    first attempt could never pay at all.
    """
    if not is_live():
        return None

    reference = payment.new_gateway_reference()
    payment.save(update_fields=["gateway_reference"])

    try:
        data = _call(
            "/transaction/initialize",
            {
                # Paystack counts in kobo, and this is the whole total: the fee
                # plus the gateway's own cut, which is what the applicant was
                # shown.
                "amount": minor_units(payment.total_ngn),
                "email": email,
                "currency": "NGN",
                "reference": reference,
                "callback_url": callback_url,
                "metadata": {
                    "application": payment.application.reference,
                    "payment": payment.reference,
                },
            },
            method="POST",
        )
    except error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode()
        except Exception:
            pass
        logger.error(
            "Paystack HTTPError %s initializing payment %s: %s",
            exc.code, payment.reference, err_body or exc
        )
        return None
    except (error.URLError, ValueError, TimeoutError, OSError) as exc:
        logger.error("Could not initialise payment %s: %s", payment.reference, exc)
        return None

    if not data.get("status"):
        logger.error(
            "Paystack refused to initialise %s: %s", payment.reference, data.get("message")
        )
        return None

    return (data.get("data") or {}).get("authorization_url")


def verify(reference):
    """Ask Paystack what happened to a reference.

    Used when the applicant comes back from the provider. A webhook can be late,
    retried, or lost behind a deploy, so the return trip does not wait for it: it
    asks. Returns the transaction dict, or None if the call failed — which is not
    the same as "not paid" and must never be treated as a failure.
    """
    if not is_live() or not reference:
        return None
    try:
        data = _call(f"/transaction/verify/{parse.quote(str(reference), safe='')}")
    except (error.URLError, error.HTTPError, ValueError, TimeoutError, OSError) as exc:
        logger.error("Could not verify %s with Paystack: %s", reference, exc)
        return None
    if not data.get("status"):
        logger.warning("Paystack could not verify %s: %s", reference, data.get("message"))
        return None
    return data.get("data") or {}


def signature_is_valid(raw_body, header_signature):
    """Whether this webhook really came from Paystack.

    Paystack signs the raw request body with HMAC-SHA512 under the secret key.
    Without checking it the webhook endpoint is a public "mark this paid" button,
    which would be worse than the hole it was added to close. Compared in constant
    time so the check cannot be probed a byte at a time, and computed over the raw
    bytes because re-serialising the JSON would change them.
    """
    if not is_live() or not header_signature:
        return False
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, str(header_signature))


def ip_is_allowed(address):
    """Whether this address may post webhooks, when an allowlist is configured.

    Empty allowlist means every address is allowed through to the signature
    check, which is the setting to use behind a proxy that does not pass the
    original address on.
    """
    allowed = getattr(settings, "PAYSTACK_WEBHOOK_IPS", None)
    if not allowed:
        return True
    return address in set(allowed)


def transaction_is_settled(data):
    """Whether this transaction dict says the money is actually in."""
    return bool(data) and data.get("status") == "success"


def amount_covers(payment, minor):
    """Whether what Paystack collected covers what was quoted.

    A signature proves the message came from Paystack. It does not prove the
    amount: someone able to start a small charge against a known reference would
    otherwise have the whole application fee settled for a fraction of it. The
    comparison is against the total in Naira, which is the number the card was
    asked for.
    """
    if minor is None:
        return False
    try:
        collected = (Decimal(minor) / 100).quantize(Decimal("0.01"))
    except (TypeError, ValueError, ArithmeticError):
        return False
    return collected >= payment.total_ngn


def currency_is_expected(data):
    """Paystack is asked for Naira, so anything else is not this transaction."""
    return (data or {}).get("currency", "NGN").upper() == "NGN"
