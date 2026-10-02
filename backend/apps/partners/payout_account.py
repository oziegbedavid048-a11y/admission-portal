"""Changing where payouts go needs the account's password, and is announced.

Payouts are sent to whatever bank account is on file when the desk pays them.
Anyone holding a stolen session could otherwise point every pending and future
payout at their own account in one request, and nobody would be told. So:

* a change to the bank name, account number or account name must carry the
  current password, checked here on the server;
* the owner is emailed whenever an existing payout account changes;
* each payout records the account it was requested for (see models.py), so
  the desk pays the account that was on file at the time of the request.
"""

from rest_framework import serializers

BANK_FIELDS = ("bank_name", "account_number", "account_name")


def bank_changes(instance, attrs):
    """The bank fields this update would actually change."""
    return [
        field
        for field in BANK_FIELDS
        if field in attrs and (attrs[field] or "") != (getattr(instance, field) or "")
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
    if all(before.get(field) == getattr(instance, field) for field in BANK_FIELDS):
        return
    from django.db import transaction

    from apps.accounts.emails import send_payout_account_changed_email

    transaction.on_commit(lambda: send_payout_account_changed_email(instance.user, instance))


def snapshot(instance):
    return {field: getattr(instance, field) for field in BANK_FIELDS}


def destination_label(profile):
    if not profile.bank_name and not profile.account_number:
        return ""
    return f"{profile.bank_name} · {profile.account_number} ({profile.account_name})"
