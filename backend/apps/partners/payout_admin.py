"""Paystack actions shared by the agent and sales manager payout screens.

Each action does one thing:

* "Approve and send through Paystack" sends payouts waiting for approval,
* "Check with Paystack" brings payouts that are Sending up to date.

Marking paid or failed by hand stays on each screen, for payouts staff pay
themselves; a payout that is Sending is never refunded by hand, because the
money may already be on its way.
"""

from django.contrib import admin, messages

from config.admin_ui import pill

from .models import Withdrawal

STATUS = Withdrawal.Status
METHOD = Withdrawal.Method


def _plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class PaystackPayoutActions:
    """Admin mixin: Paystack columns and actions for a payout screen."""

    paystack_readonly = (
        "method",
        "paystack_reference",
        "transfer_code",
        "review_reason",
        "failure_reason",
        "approved_by",
        "sent_at",
        "paid_at",
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = {STATUS.PAID: "ok", STATUS.FAILED: "bad", STATUS.PENDING: "wait", STATUS.SENDING: "info"}
        return pill(obj.get_status_display(), tone.get(obj.status, "idle"))

    @admin.display(description="How", ordering="method")
    def method_label(self, obj):
        return obj.get_method_display()

    @admin.display(description="Note")
    def note(self, obj):
        text = obj.failure_reason or (obj.review_reason if obj.status == STATUS.PENDING else "")
        return text or "—"

    @admin.action(description="Approve and send through Paystack")
    def action_approve_and_send(self, request, queryset):
        """Send payouts waiting for approval. Only Paystack payouts in review."""
        from .payouts import send

        sent = paid = refused = 0
        for withdrawal in queryset.filter(method=METHOD.PAYSTACK, status=STATUS.PENDING):
            result = send(withdrawal, approved_by=request.user)
            if result.status == STATUS.PAID:
                paid += 1
            elif result.status == STATUS.SENDING:
                sent += 1
            else:
                refused += 1
        if paid or sent:
            self.message_user(
                request,
                f"{_plural(paid, 'payout')} paid and {_plural(sent, 'payout')} on the way through Paystack.",
                messages.SUCCESS,
            )
        if refused:
            self.message_user(
                request,
                f"Paystack did not send {_plural(refused, 'payout')}. The reason is in the Note column; "
                "the money is still held.",
                messages.WARNING,
            )
        if not (paid or sent or refused):
            self.message_user(request, "Nothing to send: choose Paystack payouts that are in review.", messages.INFO)

    @admin.action(description="Check with Paystack")
    def action_check_paystack(self, request, queryset):
        """Ask Paystack where payouts that are Sending have got to."""
        from .payouts import check

        checked = 0
        for withdrawal in queryset.filter(method=METHOD.PAYSTACK, status=STATUS.SENDING):
            check(withdrawal)
            checked += 1
        self.message_user(request, f"{_plural(checked, 'payout')} checked with Paystack.", messages.INFO)
