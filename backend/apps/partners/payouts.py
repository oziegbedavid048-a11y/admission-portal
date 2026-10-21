"""Automatic payouts through Paystack, for agents and sales managers.

The rules, in the order a withdrawal meets them:

1. Only someone with a bank account verified by Paystack, paid in Naira, is
   paid automatically: an agent in Nigeria with a Naira wallet, or a sales
   manager (always paid in Naira). Everyone else is paid by staff, as before.
   So is every payout while ``PAYSTACK_PAYOUTS_ENABLED`` is off.
2. Every payout is sent at once, with no staff approval (David's rule): the
   wallet's own minimum is the only limit. It can only go to the account
   Paystack verified, and changing that account needs the password.
3. The money left their balance when they asked (see the models' ``request``),
   so it cannot be asked for twice while it is on its way.
4. A payout is only marked paid when Paystack says the transfer succeeded, and
   only refunded when Paystack says it failed or was reversed. A request that
   got no clear answer stays "Sending" and is checked by its reference; it is
   never refunded on a guess, because the money may already be on its way.
5. If Paystack refuses to send (its balance is too low, an account problem),
   nothing was sent: the payout goes back to staff review with the reason, the
   money still held, and staff can send it again or refund it.

The company pays Paystack's transfer fee, so the person receives exactly the
amount they asked for.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import paystack_transfers as paystack
from .models import AgentProfile, SupervisorWithdrawal, Withdrawal

logger = logging.getLogger(__name__)

NIGERIA = "nigeria"
STATUS = Withdrawal.Status
METHOD = Withdrawal.Method


def payouts_enabled():
    return bool(getattr(settings, "PAYSTACK_PAYOUTS_ENABLED", False)) and paystack.is_configured()


# ── Agents and sales managers, behind one shape ───────────────────────


def owner_of(withdrawal):
    """The profile being paid: an agent or a sales manager."""
    return withdrawal.agent if isinstance(withdrawal, Withdrawal) else withdrawal.supervisor


def _prefix(withdrawal):
    return "gabstep-wd" if isinstance(withdrawal, Withdrawal) else "gabstep-sm"


def _emails(withdrawal):
    from apps.accounts import emails

    if isinstance(withdrawal, Withdrawal):
        return emails.send_agent_payout_sent_email, emails.send_agent_payout_failed_email
    return emails.send_manager_payout_sent_email, emails.send_manager_payout_failed_email


def can_pay_automatically(profile):
    """Whether this agent or sales manager is paid through Paystack, and if
    not, why not."""
    if not payouts_enabled():
        return False, "Automatic payouts are switched off."
    if isinstance(profile, AgentProfile):
        if (profile.user.country or "").strip().lower() != NIGERIA:
            return False, "Automatic payouts are for agents in Nigeria."
        wallet = getattr(profile, "wallet", None)
        if (getattr(wallet, "currency", "NGN") or "NGN").upper() != "NGN":
            return False, "Automatic payouts are paid in Naira."
    if not (profile.bank_code and profile.account_verified_at and profile.account_number):
        return False, "The payout account is not verified with Paystack yet."
    return True, ""


# ── The payout's journey ──────────────────────────────────────────────


def prepare(withdrawal):
    """Decide how a new payout is paid. Called right after it is requested.

    Returns True when it should be sent to Paystack now.
    """
    profile = owner_of(withdrawal)
    automatic, _why = can_pay_automatically(profile)
    if not automatic:
        return False
    withdrawal.method = METHOD.PAYSTACK
    withdrawal.bank_code = profile.bank_code
    withdrawal.account_number = profile.account_number
    withdrawal.paystack_reference = f"{_prefix(withdrawal)}-{withdrawal.pk}-{timezone.now():%Y%m%d%H%M%S}"
    withdrawal.save(update_fields=["method", "bank_code", "account_number", "paystack_reference"])
    return True


def _recipient_code(withdrawal):
    """Paystack's recipient for the account this payout was requested to."""
    profile = owner_of(withdrawal)
    same_account = profile.bank_code == withdrawal.bank_code and profile.account_number == withdrawal.account_number
    if same_account and profile.paystack_recipient_code:
        return profile.paystack_recipient_code
    code = paystack.create_recipient(profile.account_name, withdrawal.account_number, withdrawal.bank_code)
    if same_account:
        type(profile).objects.filter(pk=profile.pk).update(paystack_recipient_code=code)
    return code


def send(withdrawal, approved_by=None):
    """Hand a payout to Paystack. Safe to call again: the reference is fixed,
    and only a payout in review (never one already sending or settled) is sent.
    """
    model = type(withdrawal)
    with transaction.atomic():
        locked = model.objects.select_for_update().get(pk=withdrawal.pk)
        if locked.method != METHOD.PAYSTACK or locked.status != STATUS.PENDING:
            return locked
        locked.status = STATUS.SENDING
        locked.sent_at = timezone.now()
        locked.failure_reason = ""
        if approved_by is not None:
            locked.approved_by = approved_by
        locked.save(update_fields=["status", "sent_at", "failure_reason", "approved_by"])

    try:
        recipient = _recipient_code(locked)
        data = paystack.send_transfer(
            locked.net_amount, recipient, locked.paystack_reference, f"Gabstep payout {locked.reference}"
        )
    except paystack.PaystackRejected as exc:
        # Paystack said no, so nothing left. Back to staff, money still held.
        logger.warning("Paystack refused payout %s: %s", locked.reference, exc)
        model.objects.filter(pk=locked.pk, status=STATUS.SENDING).update(
            status=STATUS.PENDING,
            failure_reason=f"Paystack did not send it: {exc}"[:300],
            review_reason="Paystack refused the transfer; see the reason.",
        )
        locked.refresh_from_db()
        return locked
    except paystack.PaystackUnreachable as exc:
        # No clear answer: it may have gone. Left as Sending and checked later.
        logger.error("No clear answer from Paystack for payout %s: %s", locked.reference, exc)
        return locked

    apply_transfer_status(locked, data or {})
    locked.refresh_from_db()
    return locked


def apply_transfer_status(withdrawal, data):
    """Move a payout on from what Paystack reports about its transfer.

    Used for the reply to a send, for webhooks and for a status check, so the
    same rules apply whichever arrives first, and repeats change nothing.
    """
    model = type(withdrawal)
    sent_email, failed_email = _emails(withdrawal)
    reported = (data.get("status") or "").lower()
    transfer_code = data.get("transfer_code") or ""
    if transfer_code and not withdrawal.transfer_code:
        model.objects.filter(pk=withdrawal.pk).update(transfer_code=transfer_code)

    if reported == "success":
        updated = model.objects.filter(
            pk=withdrawal.pk, status__in=[STATUS.SENDING, STATUS.PENDING]
        ).update(status=STATUS.PAID, paid_at=timezone.now(), failure_reason="", review_reason="")
        if updated:
            withdrawal.refresh_from_db()
            transaction.on_commit(lambda: sent_email(withdrawal))
        return

    if reported in ("failed", "reversed"):
        reason = "Paystack reversed the transfer." if reported == "reversed" else "Paystack could not complete the transfer."
        if withdrawal.refund(reason):
            transaction.on_commit(lambda: failed_email(withdrawal))
        return

    if reported == "otp":
        # Transfers need a one-time code on this Paystack account, so nothing
        # can be sent automatically until that is switched off.
        model.objects.filter(pk=withdrawal.pk, status=STATUS.SENDING).update(
            status=STATUS.PENDING,
            failure_reason="Paystack asked for an OTP. Turn off OTP for transfers in Paystack (Settings, Preferences).",
            review_reason="Paystack asked for an OTP.",
        )
        return
    # "pending", "received", "processing", "queued": still on its way.


def check(withdrawal):
    """Ask Paystack where a payout that is Sending has got to."""
    if withdrawal.method != METHOD.PAYSTACK or not withdrawal.paystack_reference:
        return withdrawal
    try:
        data = paystack.verify_transfer(withdrawal.paystack_reference)
    except paystack.PaystackRejected as exc:
        # Paystack has no transfer under this reference: it was never sent.
        if withdrawal.status == STATUS.SENDING and "not found" in str(exc).lower():
            type(withdrawal).objects.filter(pk=withdrawal.pk, status=STATUS.SENDING).update(
                status=STATUS.PENDING,
                failure_reason="Paystack has no transfer for this payout; it was not sent.",
                review_reason="Not sent; send it again or refund it.",
            )
        withdrawal.refresh_from_db()
        return withdrawal
    except paystack.PaystackUnreachable:
        return withdrawal
    apply_transfer_status(withdrawal, data or {})
    withdrawal.refresh_from_db()
    return withdrawal


def find_by_reference(reference):
    for model in (Withdrawal, SupervisorWithdrawal):
        found = model.objects.filter(paystack_reference=reference).first()
        if found is not None:
            return found
    return None


def handle_webhook(event, data):
    """A Paystack transfer.* webhook. The signature is already verified."""
    reference = (data or {}).get("reference") or ""
    withdrawal = find_by_reference(reference) if reference else None
    if withdrawal is None:
        logger.warning("Transfer webhook for an unknown reference %r.", reference)
        return
    amount = (data or {}).get("amount")
    if amount is not None and int(amount) != paystack.kobo(withdrawal.net_amount):
        logger.error(
            "Transfer webhook for %s reported %r kobo, not %s.",
            withdrawal.reference, amount, paystack.kobo(withdrawal.net_amount),
        )
        return
    status_for = {"transfer.success": "success", "transfer.failed": "failed", "transfer.reversed": "reversed"}
    with transaction.atomic():
        apply_transfer_status(withdrawal, {**data, "status": status_for.get(event, data.get("status"))})
