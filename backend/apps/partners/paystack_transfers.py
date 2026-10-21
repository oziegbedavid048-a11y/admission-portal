"""Paying agents through Paystack Transfers.

Paystack's side of an agent payout, kept to the five calls it needs:

  * the list of Nigerian banks, so an agent picks theirs instead of typing it,
  * resolving an account number, so the name on the account is Paystack's,
    not whatever was typed,
  * creating a transfer recipient for that account,
  * sending a transfer from the Paystack balance,
  * verifying a transfer by its reference.

Everything is in Naira to Nigerian banks: a Nigerian Paystack account pays
nowhere else. The secret key is the same one that collects application fees
(``PAYSTACK_SECRET_KEY``). Paystack decides test or live from the key.

Errors are raised as ``PaystackRejected`` when Paystack answered and said no
(insufficient balance, a bad account), and ``PaystackUnreachable`` when no clear
answer came back (a timeout, a dropped connection). The difference matters: a
rejected transfer was not sent, while an unreachable one may have been, so it is
checked by reference before anything is refunded.
"""

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from urllib import error, parse

from django.conf import settings
from django.core.cache import cache

from apps.payments.gateway import _call

logger = logging.getLogger(__name__)

BANKS_CACHE_KEY = "paystack:banks:nigeria"
BANKS_TTL = 60 * 60 * 24


class PaystackRejected(Exception):
    """Paystack answered and refused. Nothing was sent."""


class PaystackUnreachable(Exception):
    """No clear answer from Paystack. The transfer may or may not exist."""


def is_configured():
    return bool(getattr(settings, "PAYSTACK_SECRET_KEY", ""))


def _request(path, payload=None, method="GET"):
    if not is_configured():
        raise PaystackRejected("Paystack is not configured.")
    try:
        answer = _call(path, payload, method)
    except error.HTTPError as exc:
        # Paystack's refusals come back as 4xx with a JSON message.
        try:
            message = json.loads(exc.read().decode()).get("message") or str(exc)
        except Exception:
            message = str(exc)
        if 400 <= exc.code < 500:
            raise PaystackRejected(message) from exc
        raise PaystackUnreachable(message) from exc
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise PaystackUnreachable(str(exc)) from exc
    if not answer.get("status"):
        raise PaystackRejected(answer.get("message") or "Paystack refused the request.")
    return answer.get("data")


def kobo(amount_ngn):
    return int((Decimal(amount_ngn) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def list_banks():
    """Nigerian banks Paystack can pay: [{"name", "code"}], cached for a day."""
    banks = cache.get(BANKS_CACHE_KEY)
    if banks is not None:
        return banks
    query = parse.urlencode({"country": "nigeria", "currency": "NGN", "perPage": 200, "use_cursor": "false"})
    data = _request(f"/bank?{query}") or []
    banks = sorted(
        ({"name": bank["name"], "code": bank["code"]} for bank in data if bank.get("code") and bank.get("active", True)),
        key=lambda bank: bank["name"].lower(),
    )
    cache.set(BANKS_CACHE_KEY, banks, BANKS_TTL)
    return banks


def bank_name_for(code):
    return next((bank["name"] for bank in list_banks() if bank["code"] == code), "")


def resolve_account(account_number, bank_code):
    """The name on this account, as the bank holds it."""
    query = parse.urlencode({"account_number": account_number, "bank_code": bank_code})
    data = _request(f"/bank/resolve?{query}")
    name = (data or {}).get("account_name", "").strip()
    if not name:
        raise PaystackRejected("That account could not be found.")
    return name


def create_recipient(name, account_number, bank_code):
    data = _request(
        "/transferrecipient",
        {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN",
        },
        method="POST",
    )
    return data["recipient_code"]


def send_transfer(amount_ngn, recipient_code, reference, reason):
    """Start a transfer from the Paystack balance. Returns Paystack's data.

    The reference is ours and unique per payout, so Paystack refuses a second
    transfer with the same one: a retry can never pay twice.
    """
    return _request(
        "/transfer",
        {
            "source": "balance",
            "amount": kobo(amount_ngn),
            "currency": "NGN",
            "recipient": recipient_code,
            "reference": reference,
            "reason": reason[:100],
        },
        method="POST",
    )


def verify_transfer(reference):
    return _request(f"/transfer/verify/{parse.quote(reference)}")
