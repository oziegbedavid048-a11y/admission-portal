"""Signing the Sales Partnership Contract in the portal.

A new agent meets the contract the first time they open the portal and cannot
use anything else until it is signed. Their name, email, phone and address are
already on it from sign-up; they add a signature (drawn, or their typed name in
a handwriting style) and the date is the day they sign.

Signing builds the final PDF, stores it, emails the agent a copy and opens the
portal. Commission amounts are in Naira; for an agent outside Nigeria clause 7
also shows estimates in their own currency at the rate of the day, and that rate
is kept with the contract so the signed copy never changes.
"""

import base64
import binascii
import io
import logging
import threading

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.applications.constants import AGENT_REGISTRATION_COMMISSION_NGN, AGENT_VISA_COMMISSION_NGN

from .contract_pdf import build_contract_pdf, contract_terms
from .models import AgentContract

logger = logging.getLogger(__name__)

# A drawn signature is a small PNG; anything far bigger is not one.
MAX_SIGNATURE_BYTES = 600 * 1024
PNG_PREFIX = "data:image/png;base64,"
# Narrower than this (in pixels, on a canvas drawn 1200 wide) is not a signature.
MIN_SIGNATURE_WIDTH = 40


class ContractError(ValueError):
    """A signing request that cannot be accepted, with a message for the agent."""


def _currency_and_rate(agent):
    from .currency import NAIRA, naira_per_unit

    wallet = getattr(agent, "wallet", None)
    currency = (getattr(wallet, "currency", "") or NAIRA).upper()
    if currency == NAIRA:
        return NAIRA, None
    try:
        return currency, naira_per_unit(currency)
    except ValueError:
        # No rate on file: the contract shows Naira only rather than a guess.
        return NAIRA, None


def details_for(agent):
    user = agent.user
    return {
        "name": (user.full_name or "").strip(),
        "email": user.email,
        "phone": (user.phone or "").strip(),
        "address": (agent.address or "").strip(),
        "country": (user.country or "").strip(),
    }


def preview_pdf(agent):
    """The contract as the agent will sign it today, without a signature."""
    currency, rate = _currency_and_rate(agent)
    details = details_for(agent)
    return build_contract_pdf(
        name=details["name"],
        email=details["email"],
        phone=details["phone"],
        address=details["address"],
        signed_on=timezone.localdate(),
        terms=contract_terms(AGENT_REGISTRATION_COMMISSION_NGN, AGENT_VISA_COMMISSION_NGN, currency, rate),
    )


def decode_signature(data_url):
    """The PNG bytes of a signature sent as a data URL, checked."""
    from PIL import Image

    if not isinstance(data_url, str) or not data_url.startswith(PNG_PREFIX):
        raise ContractError("Add your signature before signing.")
    try:
        raw = base64.b64decode(data_url[len(PNG_PREFIX):], validate=True)
    except (binascii.Error, ValueError):
        raise ContractError("That signature could not be read. Clear it and sign again.")
    if len(raw) > MAX_SIGNATURE_BYTES:
        raise ContractError("That signature is too large. Clear it and sign again.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        raise ContractError("That signature could not be read. Clear it and sign again.")
    # A blank canvas has no ink at all, and a dot or a smudge is not a signature.
    box = image.getchannel("A").getbbox()
    if box is None or (box[2] - box[0]) < MIN_SIGNATURE_WIDTH:
        raise ContractError("Add your signature before signing.")
    return raw


@transaction.atomic
def sign(agent, *, signature_png, method, address=None, ip_address=None, user_agent=""):
    """Sign the contract for `agent`. Returns the AgentContract."""
    agent = type(agent).objects.select_for_update().get(pk=agent.pk)
    existing = AgentContract.objects.filter(agent=agent).first()
    if existing is not None and existing.file:
        raise ContractError("Your contract is already signed.")
    if method not in AgentContract.Method.values:
        raise ContractError("Choose how you want to sign.")

    address = (address or "").strip()
    if address and address != agent.address:
        agent.address = address[:255]
        agent.save(update_fields=["address"])
    details = details_for(agent)
    if not details["address"]:
        raise ContractError("Enter your address. It is printed on the contract.")

    currency, rate = _currency_and_rate(agent)
    today = timezone.localdate()
    pdf = build_contract_pdf(
        name=details["name"],
        email=details["email"],
        phone=details["phone"],
        address=details["address"],
        signed_on=today,
        terms=contract_terms(AGENT_REGISTRATION_COMMISSION_NGN, AGENT_VISA_COMMISSION_NGN, currency, rate),
        signature_png=signature_png,
    )

    contract = existing or AgentContract(agent=agent)
    contract.source = AgentContract.Source.PORTAL
    contract.signed_on = today
    contract.signed_at = timezone.now()
    contract.signer_name = details["name"]
    contract.signer_email = details["email"]
    contract.signer_phone = details["phone"]
    contract.signer_address = details["address"]
    contract.signature_method = method
    contract.currency = currency
    contract.ngn_per_unit = rate
    contract.ip_address = ip_address
    contract.user_agent = (user_agent or "")[:255]
    contract.file.save(contract.filename, ContentFile(pdf), save=False)
    contract.save()

    transaction.on_commit(lambda: _email_copy_later(contract.pk, pdf))
    return contract


def _email_copy_later(contract_pk, pdf):
    """Email the copy off the request thread, so signing answers at once."""
    from django.conf import settings

    if getattr(settings, "TESTING", False):
        _email_copy(contract_pk, pdf)
        return
    threading.Thread(target=_email_copy, args=(contract_pk, pdf), daemon=True).start()


def _email_copy(contract_pk, pdf):
    from django.db import connection

    from apps.accounts.emails import send_contract_signed_email

    try:
        contract = AgentContract.objects.select_related("agent__user").get(pk=contract_pk)
        if send_contract_signed_email(contract, pdf):
            AgentContract.objects.filter(pk=contract_pk).update(emailed_at=timezone.now())
    except Exception:
        logger.exception("Could not email the signed contract %s", contract_pk)
    finally:
        if threading.current_thread() is not threading.main_thread():
            connection.close()
