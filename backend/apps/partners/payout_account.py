"""Changing where payouts go needs the account's password, and is announced.

Payouts are sent to whatever bank account is on file when the desk pays them.
Anyone holding a stolen session could otherwise point every pending and future
payout at their own account in one request, and nobody would be told. So:

* a change to the bank name, account number or account name must carry the
  current password, checked here on the server;
* the owner is emailed whenever an existing payout account changes;
* each payout records the account it was requested for (see models.py), so
  the desk pays the account that was on file at the time of the request;
* withdrawals pause for ``PAYOUT_HOLD_HOURS_AFTER_BANK_CHANGE`` hours after
  payouts are pointed at a different account. Payouts go out instantly with
  no staff approval, so without this a stolen password could change the bank
  and empty the balance in a minute, before the owner reads the email.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import serializers

BANK_FIELDS = ("bank_name", "account_number", "account_name", "bank_code")


def bank_changes(instance, attrs):
    """The bank fields this update would actually change."""
    return [
        field
        for field in BANK_FIELDS
        if field in attrs and (attrs[field] or "") != (getattr(instance, field, "") or "")
    ]


def check_password_for_bank_change(serializer, instance, attrs):
    """Raise unless a bank change is confirmed with the current password."""
    password = attrs.pop("current_password", "")
    if instance is None or not bank_changes(instance, attrs):
        return attrs
    user = serializer.context["request"].user
    if not password:
        raise serializers.ValidationError(
            {"current_password": "Enter your password to change your payment account."}
        )
    if not user.check_password(password):
        raise serializers.ValidationError({"current_password": "That password is not correct."})
    return attrs


def announce_bank_change(instance, before):
    """Email the owner when an existing payout account was changed."""
    if not any(before.get(field) for field in BANK_FIELDS):
        return  # First time it is set: nothing was redirected.
    if all(before.get(field) == getattr(instance, field, "") for field in BANK_FIELDS):
        return
    from django.db import transaction

    from apps.accounts.emails import send_payout_account_changed_email

    transaction.on_commit(lambda: send_payout_account_changed_email(instance.user, instance))


def snapshot(instance):
    # Sales managers have no bank code; only agents are paid through Paystack.
    return {field: getattr(instance, field, "") for field in BANK_FIELDS}


def destination_label(profile):
    if not profile.bank_name and not profile.account_number:
        return ""
    return f"{profile.bank_name} · {profile.account_number} ({profile.account_name})"


def verify_bank_with_paystack(serializer, instance, attrs):
    """A bank picked from Paystack's list is checked with Paystack before it is
    saved: the account must exist at that bank, and the name saved is the name
    the bank holds, not what was typed. Sets ``serializer._verified``."""
    from . import paystack_transfers as paystack

    serializer._verified = False
    code = (attrs.get("bank_code") or "").strip()
    number = attrs.get("account_number", getattr(instance, "account_number", ""))
    changing = any(
        field in attrs and (attrs[field] or "") != (getattr(instance, field, "") or "")
        for field in ("bank_code", "account_number")
    )
    if not code or not changing or not paystack.is_configured():
        return attrs
    try:
        name = paystack.resolve_account(number, code)
        bank = paystack.bank_name_for(code)
    except paystack.PaystackRejected:
        raise serializers.ValidationError(
            {"account_number": "Paystack could not find this account at that bank. Check the number and the bank."}
        )
    except paystack.PaystackUnreachable:
        raise serializers.ValidationError(
            {"account_number": "The account could not be checked right now. Please try again in a moment."}
        )
    attrs["account_name"] = name[:120]
    if bank:
        attrs["bank_name"] = bank[:120]
    serializer._verified = True
    return attrs


def _same(a, b):
    return " ".join((a or "").split()).lower() == " ".join((b or "").split()).lower()


def points_elsewhere(before, after):
    """Whether payouts would now go to a different account than before.

    Confirming the account typed at sign-up (same number, same bank) is not a
    change of destination."""
    if not before.get("account_number"):
        return False  # First account on file: nothing is redirected.
    return not (
        _same(before.get("account_number"), after.get("account_number"))
        and _same(before.get("bank_name"), after.get("bank_name"))
    )


def withdrawal_hold_until(profile):
    """When withdrawals open again after a payout-account change, or None."""
    changed = getattr(profile, "payout_account_changed_at", None)
    hours = int(getattr(settings, "PAYOUT_HOLD_HOURS_AFTER_BANK_CHANGE", 24) or 0)
    if not changed or hours <= 0:
        return None
    until = changed + timedelta(hours=hours)
    return until if until > timezone.now() else None


def check_withdrawal_hold(profile):
    """Raise while a recent payout-account change is still on hold."""
    until = withdrawal_hold_until(profile)
    if until is not None:
        local = timezone.localtime(until)
        raise ValidationError(
            "Your payout account changed recently, so withdrawals are paused for your safety. "
            f"You can withdraw from {local:%d %b, %H:%M}."
        )


# Written by reset_verification when bank details change, so they are saved
# along with whatever the person edited.
VERIFICATION_FIELDS = ("account_verified_at", "paystack_recipient_code", "bank_code", "payout_account_changed_at")


def save_profile(instance, validated_data):
    """Save a profile edit, writing only the columns the edit touched.

    The profile was read when the request began. Saving every column wrote that
    old copy back: a sales manager's `total_withdrawn` from before a payout in
    another tab, or a `bonus_total` from before a bonus landed, so the same
    balance could be withdrawn twice. The same went for the user row, where an
    old copy could undo a password change or a deactivation made meanwhile.
    """
    user_data = validated_data.pop("user", {})
    if user_data:
        for field, value in user_data.items():
            setattr(instance.user, field, value)
        instance.user.save(update_fields=list(user_data))
    for field, value in validated_data.items():
        setattr(instance, field, value)
    fields = set(validated_data) | set(VERIFICATION_FIELDS)
    instance.save(update_fields=sorted(fields))
    return instance, user_data


def reset_verification(serializer, instance, validated_data, before):
    """New bank details are verified only if Paystack just confirmed them, and
    the old Paystack recipient no longer applies either way."""
    changed = any(
        field in validated_data and (validated_data[field] or "") != (before.get(field) or "")
        for field in ("bank_code", "account_number", "bank_name", "account_name")
    )
    if not changed:
        return
    verified = getattr(serializer, "_verified", False)
    instance.account_verified_at = timezone.now() if verified else None
    instance.paystack_recipient_code = ""
    if not verified and "bank_code" not in validated_data:
        instance.bank_code = ""
    after = {field: validated_data.get(field, before.get(field)) for field in BANK_FIELDS}
    if points_elsewhere(before, after):
        instance.payout_account_changed_at = timezone.now()
