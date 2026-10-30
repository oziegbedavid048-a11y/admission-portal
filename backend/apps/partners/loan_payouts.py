"""Paying an Ads funding loan straight into a Meta ads invoice, through Paystack.

The rules, in the order a loan meets them:

1. Only an agent in Nigeria with a Naira wallet, while Paystack is connected,
   gives a Meta invoice (``meta_invoice_offered``). Everyone else is funded
   by staff by hand, as before.
2. The agent asks for an amount and a platform only. The desk approves it
   ("Approve for Meta" in the admin, ``approve_for_invoice``): nothing is paid,
   the loan's Paystack reference is fixed, and the agent is emailed.
3. The agent then creates the Meta invoice for exactly the approved amount,
   gives its details on the dashboard and presses Pay (``pay_invoice``).
   Paystack resolves the account and the name must belong to Meta/Facebook
   ("Meta Ads" for EBANX invoices); then it is paid at once, under the
   reference fixed for that loan, so it can never be paid twice. Paying the
   moment the invoice exists means it cannot expire while waiting for review.
4. The loan only counts against the agent (their loan balance) when Paystack
   says the transfer succeeded. Failed or reversed means nothing is owed.
5. A refusal is only treated as "nothing sent" after Paystack confirms it
   holds no transfer under the reference. A low Paystack balance holds the
   loan as approved, and check_payouts sends it again once topped up.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from . import paystack_transfers as paystack
from .models import Loan, Wallet
from .payouts import LOW_BALANCE_NOTE, NIGERIA, UNKNOWN, is_low_balance

logger = logging.getLogger(__name__)

STATUS = Loan.Status
PREFIX = "gabstep-ln-"


def meta_invoice_offered(agent):
    """Whether this agent's Ads funding is paid to a Meta invoice through Paystack.

    Only needs Paystack to be connected: it does not wait for automatic
    withdrawals (PAYSTACK_PAYOUTS_ENABLED) to be switched on, because nothing
    is paid without the desk's approval anyway.
    """
    if not paystack.is_configured():
        return False
    if (agent.user.country or "").strip().lower() != NIGERIA:
        return False
    wallet = getattr(agent, "wallet", None)
    return (getattr(wallet, "currency", "NGN") or "NGN").upper() == "NGN"


def is_meta_account_name(name):
    """Whether a bank account name, as Paystack returns it, is Meta's.

    Meta's invoice accounts change bank, number and name ("Meta Ads",
    "E3X META NG", "EBANX / Meta Ads", "Facebook ..."), but the name always
    has Meta in it. So "Meta" or "Facebook" as a whole word anywhere in the
    name is accepted; letters inside another word ("Metallic Ventures") are
    not. The agent also sees the resolved name and confirms it matches their
    invoice before paying. Exact names the desk adds in META_ACCOUNT_NAMES
    (comma separated) are accepted too.
    """
    import re

    from django.conf import settings

    words = re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).split()
    if not words:
        return False
    extra = {
        " ".join(re.sub(r"[^A-Z0-9]+", " ", item.upper()).split())
        for item in (getattr(settings, "META_ACCOUNT_NAMES", "") or "").split(",")
        if item.strip()
    }
    if " ".join(words) in extra:
        return True
    return bool({"META", "FACEBOOK"} & set(words))


def still_meta(loan):
    """Re-check the invoice account with Paystack just before paying it.

    Invoice accounts are temporary and can be handed on once an invoice
    expires; the money must only leave if the account is still Meta's.
    Returns (ok, reason).
    """
    try:
        name = paystack.resolve_account(loan.meta_account_number, loan.meta_bank_code)
    except paystack.PaystackRejected:
        return False, "Paystack no longer finds the Meta invoice account; ask the agent for a new invoice."
    except paystack.PaystackUnreachable:
        return False, "Paystack could not be reached to re-check the Meta account; try again shortly."
    if not is_meta_account_name(name):
        return False, f"The invoice account is now in the name of {name[:60]}, not Meta; nothing was sent."
    return True, ""


def _transfer(loan):
    """What Paystack holds under this loan's reference (see payouts.paystack_transfer)."""
    if not loan.paystack_reference:
        return None
    try:
        data = paystack.verify_transfer(loan.paystack_reference)
    except paystack.PaystackRejected as exc:
        return None if "not found" in str(exc).lower() else UNKNOWN
    except paystack.PaystackUnreachable:
        return UNKNOWN
    return data if isinstance(data, dict) and data else UNKNOWN


def approve_and_send(loan, approved_by):
    """The desk's approval: lock it, fix its reference, and pay Meta. Returns the loan."""
    with transaction.atomic():
        locked = Loan.objects.select_for_update().get(pk=loan.pk)
        if locked.status not in (STATUS.PENDING, STATUS.APPROVED) or not locked.pays_meta:
            return locked
        if locked.invoice_expires_at and locked.invoice_expires_at <= timezone.now():
            locked.review_reason = "The Meta invoice has expired; ask the agent for a new one."
            locked.save(update_fields=["review_reason"])
            return locked
        ok, why = still_meta(locked)
        if not ok:
            locked.review_reason = why[:200]
            locked.save(update_fields=["review_reason"])
            return locked
        locked.status = STATUS.APPROVED
        locked.approved_amount = locked.requested_amount
        locked.approved_by = approved_by
        if not locked.paystack_reference:
            locked.paystack_reference = f"{PREFIX}{locked.pk}-{timezone.now():%Y%m%d%H%M%S}"
        locked.save(update_fields=["status", "approved_amount", "approved_by", "paystack_reference", "review_reason"])
    return send(locked)


def approve_for_invoice(loan, approved_by):
    """The desk's approval of a request with no invoice yet. Pays nothing.

    Fixes the amount and the Paystack reference, and emails the agent to give
    the Meta invoice. Returns the loan.
    """
    from apps.accounts.emails import send_loan_ready_for_invoice_email

    with transaction.atomic():
        locked = Loan.objects.select_for_update().get(pk=loan.pk)
        if locked.status != STATUS.PENDING or locked.pays_meta:
            return locked
        locked.status = STATUS.APPROVED
        locked.approved_amount = locked.requested_amount
        locked.approved_by = approved_by
        locked.invoice_expires_at = None
        locked.review_reason = ""
        locked.paystack_reference = f"{PREFIX}{locked.pk}-{timezone.now():%Y%m%d%H%M%S}"
        locked.save(update_fields=[
            "status", "approved_amount", "approved_by", "invoice_expires_at", "review_reason", "paystack_reference",
        ])
        transaction.on_commit(lambda: send_loan_ready_for_invoice_email(locked))
    return locked


def pay_invoice(loan, details):
    """The agent's Pay: store the checked Meta invoice and send it through Paystack.

    ``details`` comes from PayMetaInvoiceSerializer (already resolved to an
    account in Meta's name). Only an approved loan waiting for its invoice is
    paid; anything else is returned untouched. Returns the loan.
    """
    with transaction.atomic():
        locked = Loan.objects.select_for_update().get(pk=loan.pk)
        if not locked.awaiting_invoice:
            return locked
        for field in ("ad_account_link", "meta_bank_code", "meta_account_number", "meta_account_name", "meta_bank_name"):
            setattr(locked, field, details[field])
        locked.review_reason = ""
        locked.save(update_fields=[
            "ad_account_link", "meta_bank_code", "meta_account_number", "meta_account_name", "meta_bank_name",
            "review_reason",
        ])
    return send(locked)


def send(loan):
    """Hand an approved loan to Paystack. Safe to call again (fixed reference)."""
    with transaction.atomic():
        locked = Loan.objects.select_for_update().get(pk=loan.pk)
        if locked.status != STATUS.APPROVED or not locked.paystack_reference or not locked.pays_meta:
            return locked
        locked.status = STATUS.SENDING
        locked.sent_at = timezone.now()
        locked.failure_reason = ""
        locked.save(update_fields=["status", "sent_at", "failure_reason"])

    try:
        recipient = paystack.create_recipient(
            locked.meta_account_name, locked.meta_account_number, locked.meta_bank_code
        )
        data = paystack.send_transfer(
            locked.approved_amount or locked.requested_amount,
            recipient,
            locked.paystack_reference,
            f"Gabstep ads funding {locked.reference}",
        )
    except paystack.PaystackRejected as exc:
        logger.warning("Paystack refused ads funding %s: %s", locked.reference, exc)
        found = _transfer(locked)
        if found is UNKNOWN:
            return locked  # left Sending; check_payouts asks again
        if found is not None:
            apply_status(locked, found)
            locked.refresh_from_db()
            return locked
        Loan.objects.filter(pk=locked.pk, status=STATUS.SENDING).update(
            status=STATUS.APPROVED,
            failure_reason=f"Paystack did not send it: {exc}"[:300],
            review_reason=LOW_BALANCE_NOTE if is_low_balance(str(exc)) else "Paystack refused the transfer; see the reason.",
        )
        locked.refresh_from_db()
        return locked
    except paystack.PaystackUnreachable as exc:
        logger.error("No clear answer from Paystack for ads funding %s: %s", locked.reference, exc)
        return locked
    except Exception:  # noqa: BLE001 - an answer this code did not expect
        logger.exception("Unexpected error paying ads funding %s; left as Sending.", locked.reference)
        return locked

    apply_status(locked, data if isinstance(data, dict) else {})
    locked.refresh_from_db()
    return locked


@transaction.atomic
def apply_status(loan, data):
    """Move a loan on from what Paystack reports about its transfer. Repeats change nothing."""
    locked = Loan.objects.select_for_update().get(pk=loan.pk)
    reported = (data.get("status") or "").lower()
    if data.get("transfer_code") and not locked.transfer_code:
        locked.transfer_code = data["transfer_code"]
        locked.save(update_fields=["transfer_code"])

    if reported == "success":
        if locked.status in (STATUS.SENDING, STATUS.APPROVED):
            amount = locked.approved_amount or locked.requested_amount
            locked.status = STATUS.DISBURSED
            locked.disbursed_at = timezone.now()
            locked.failure_reason = ""
            locked.review_reason = ""
            locked.save(update_fields=["status", "disbursed_at", "failure_reason", "review_reason"])
            # Owed only now that Meta has the money.
            wallet, _ = Wallet.objects.get_or_create(agent_id=locked.agent_id)
            Wallet.objects.filter(pk=wallet.pk).update(loan_balance=F("loan_balance") + amount)
            from apps.accounts.emails import send_loan_approved_email

            transaction.on_commit(lambda: send_loan_approved_email(locked))
        return

    if reported in ("failed", "reversed"):
        was_disbursed = locked.status == STATUS.DISBURSED
        if locked.status in (STATUS.FAILED, STATUS.REPAID, STATUS.DECLINED):
            return
        locked.status = STATUS.FAILED
        locked.failure_reason = (
            "Paystack reversed the payment to Meta." if reported == "reversed" else "Paystack could not pay the Meta invoice."
        )
        locked.save(update_fields=["status", "failure_reason"])
        if was_disbursed:
            # The money came back from Meta, so nothing is owed for it.
            amount = locked.approved_amount or locked.requested_amount
            wallet = Wallet.objects.select_for_update().filter(agent_id=locked.agent_id).first()
            if wallet is not None:
                wallet.loan_balance = max(wallet.loan_balance - amount, 0)
                wallet.save(update_fields=["loan_balance"])
        return

    if reported == "otp":
        Loan.objects.filter(pk=locked.pk, status=STATUS.SENDING).update(
            status=STATUS.APPROVED,
            failure_reason="Paystack asked for an OTP. Turn off OTP for transfers in Paystack (Settings, Preferences).",
            review_reason="Paystack asked for an OTP.",
        )
    # "pending", "received", "processing", "queued": still on its way.


def check(loan):
    """Ask Paystack where a loan that is Sending has got to."""
    found = _transfer(loan)
    if found is UNKNOWN:
        return loan
    if found is None:
        if loan.status == STATUS.SENDING:
            Loan.objects.filter(pk=loan.pk, status=STATUS.SENDING).update(
                status=STATUS.APPROVED,
                failure_reason="Paystack has no transfer for this loan; it was not sent.",
                review_reason="Not sent; send it again or decline it.",
            )
        loan.refresh_from_db()
        return loan
    apply_status(loan, found)
    loan.refresh_from_db()
    return loan


def handle_webhook(event, data):
    """A Paystack transfer.* webhook for a loan (reference starts gabstep-ln-)."""
    reference = (data or {}).get("reference") or ""
    loan = Loan.objects.filter(paystack_reference=reference).first() if reference else None
    if loan is None:
        logger.warning("Transfer webhook for an unknown loan reference %r.", reference)
        return
    amount = (data or {}).get("amount")
    try:
        amount = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        logger.error("Loan webhook for %s carried an unreadable amount %r.", loan.reference, amount)
        return
    expected = paystack.kobo(loan.approved_amount or loan.requested_amount)
    if amount is not None and amount != expected:
        logger.error("Loan webhook for %s reported %r kobo, not %s.", loan.reference, amount, expected)
        return
    status_for = {"transfer.success": "success", "transfer.failed": "failed", "transfer.reversed": "reversed"}
    apply_status(loan, {**data, "status": status_for.get(event, data.get("status"))})


def resend_low_balance(older_than_minutes=10):
    """Send again the approved loans held because the Paystack balance was low."""
    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
    resent = 0
    for loan in Loan.objects.filter(
        status=STATUS.APPROVED, review_reason=LOW_BALANCE_NOTE, sent_at__lte=cutoff
    ).exclude(paystack_reference=None):
        result = send(loan)
        resent += 1
        if result.review_reason == LOW_BALANCE_NOTE:
            break
    return resent
