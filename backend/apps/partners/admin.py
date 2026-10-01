"""Partner operations: approving ads funding and releasing payouts.

Both actions move real money, so both are deliberate: a loan is approved and
disbursed in one reviewed step that credits the agent's loan balance, and a
withdrawal is only marked paid once it has actually left the account.
"""

from decimal import Decimal

from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import format_html

from config.admin_ui import pill

from apps.accounts.emails import (
    send_agent_payout_failed_email,
    send_agent_payout_sent_email,
    send_loan_approved_email,
    send_loan_declined_email,
)

from .models import AgentProfile, Commission, Loan, Wallet, Withdrawal


def _plural(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _naira(value):
    return f"₦{Decimal(value or 0):,.0f}"


def _pill(text, tone):
    return pill(text, tone)


class WalletInline(admin.StackedInline):
    model = Wallet
    can_delete = False
    readonly_fields = ("available", "updated_at")
    fields = (
        ("registration_commission_total", "visa_commission_total"),
        ("total_earned", "available"),
        ("loan_balance", "loan_repaid_total"),
        ("saved_balance", "total_withdrawn"),
        "updated_at",
    )

    @admin.display(description="Available to withdraw")
    def available(self, obj):
        return _naira(obj.available_balance)


class CommissionInline(admin.TabularInline):
    model = Commission
    extra = 0
    can_delete = False
    fields = ("application", "kind", "amount", "earned_at")
    readonly_fields = ("application", "kind", "amount", "earned_at")
    max_num = 0
    ordering = ("-earned_at",)


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "partner_code",
        "user",
        "supervisor",
        "agency_name",
        "students",
        "earned",
        "owing",
        "bank_name",
        "created_at",
    )
    search_fields = ("user__full_name", "user__email", "agency_name", "account_number")
    list_filter = ("supervisor",)
    autocomplete_fields = ("user", "supervisor")
    readonly_fields = ("partner_code", "created_at")
    inlines = (WalletInline, CommissionInline)

    fieldsets = (
        (None, {"fields": ("user", "partner_code", "agency_name", "supervisor", "total_closed_sales", "created_at")}),
        ("Payout account", {"fields": ("bank_name", "account_number", "account_name")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "wallet", "supervisor__user")

    @admin.display(description="Students")
    def students(self, obj):
        return obj.applications.count()

    @admin.display(description="Earned")
    def earned(self, obj):
        return _naira(obj.wallet.total_earned)

    @admin.display(description="Loan owed")
    def owing(self, obj):
        balance = obj.wallet.loan_balance
        return _pill(_naira(balance), "wait" if balance else "idle")


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    """Ads funding requests waiting on a decision."""

    list_display = ("reference", "agent", "requested", "purpose", "campaign", "status_badge", "requested_at")
    list_filter = ("status", "purpose", "requested_at")
    search_fields = ("agent__user__full_name", "agent__user__email", "purpose")
    autocomplete_fields = ("agent",)
    date_hierarchy = "requested_at"
    readonly_fields = ("reference", "requested_at", "disbursed_at", "campaign")
    actions = ("action_approve_and_disburse", "action_mark_repaid", "action_decline")

    fieldsets = (
        (None, {"fields": ("reference", "agent", "status")}),
        ("Request", {"fields": ("requested_amount", "purpose", "ad_account_link", "campaign")}),
        ("Disbursement", {"fields": ("approved_amount", "requested_at", "disbursed_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("agent__user", "agent__wallet")

    @admin.display(description="Requested", ordering="requested_amount")
    def requested(self, obj):
        return _naira(obj.requested_amount)

    @admin.display(description="Campaign")
    def campaign(self, obj):
        if not obj.ad_account_link:
            return "None"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Review the ad</a>', obj.ad_account_link
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = {
            Loan.Status.DISBURSED: "ok",
            Loan.Status.REPAID: "ok",
            Loan.Status.DECLINED: "bad",
            Loan.Status.PENDING: "wait",
        }.get(obj.status, "idle")
        return _pill(obj.get_status_display(), tone)

    @admin.action(description="Approve and disburse the full amount")
    @transaction.atomic
    def action_approve_and_disburse(self, request, queryset):
        released = Decimal("0")
        count = 0
        # Locked, so two staff approving at once cannot release a loan twice.
        loans = queryset.select_for_update().exclude(
            status__in=(Loan.Status.DISBURSED, Loan.Status.REPAID)
        )
        for loan in loans:
            loan.status = Loan.Status.DISBURSED
            loan.approved_amount = loan.requested_amount
            loan.disbursed_at = timezone.now()
            loan.save()

            # Added in the database, so a withdrawal made at the same moment is
            # not overwritten by this copy of the wallet.
            Wallet.objects.get_or_create(agent=loan.agent)
            Wallet.objects.filter(agent=loan.agent).update(
                loan_balance=F("loan_balance") + loan.approved_amount
            )

            released += loan.approved_amount
            count += 1
            # Queued after the write so the agent is only told about money that
            # is actually in their balance.
            transaction.on_commit(lambda loan=loan: send_loan_approved_email(loan))

        self.message_user(
            request,
            f"{_plural(count, 'loan')} disbursed, {_naira(released)} released.",
            messages.SUCCESS if count else messages.INFO,
        )

    @admin.action(description="Mark as repaid")
    @transaction.atomic
    def action_mark_repaid(self, request, queryset):
        """Record that an agent has paid back their Ads funding.

        Nothing is taken from withdrawals, so this is how a loan is cleared.
        Each loan is locked and re-read, so it is only ever cleared once.
        """
        count = 0
        for loan in queryset.select_for_update().filter(status=Loan.Status.DISBURSED):
            loan.status = Loan.Status.REPAID
            loan.save(update_fields=["status"])
            wallet = Wallet.objects.select_for_update().filter(agent=loan.agent).first()
            if wallet is not None:
                wallet.loan_balance = max(
                    Decimal("0.00"), wallet.loan_balance - (loan.approved_amount or Decimal("0.00"))
                )
                wallet.save(update_fields=["loan_balance"])
            count += 1
        self.message_user(
            request,
            f"{_plural(count, 'loan')} marked as repaid.",
            messages.SUCCESS if count else messages.INFO,
        )

    @admin.action(description="Decline request")
    def action_decline(self, request, queryset):
        pending = list(queryset.filter(status=Loan.Status.PENDING).select_related("agent__user"))
        count = Loan.objects.filter(pk__in=[loan.pk for loan in pending]).update(
            status=Loan.Status.DECLINED
        )
        for loan in pending:
            send_loan_declined_email(loan)
        self.message_user(request, f"{_plural(count, 'request')} declined.", messages.WARNING)


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """Payouts waiting to be sent to an agent's bank account."""

    list_display = (
        "reference",
        "agent",
        "requested",
        "deduction",
        "net",
        "destination",
        "status_badge",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("agent__user__full_name", "agent__user__email", "agent__account_number")
    autocomplete_fields = ("agent",)
    date_hierarchy = "created_at"
    readonly_fields = (
        "reference",
        "agent",
        "amount_requested",
        "loan_deduction",
        "net_amount",
        "destination",
        # Moved only by the actions below. Editing it by hand could turn a paid
        # payout back to pending and then refund it.
        "status",
        "created_at",
    )
    actions = ("action_mark_paid", "action_mark_failed")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("agent__user")

    @admin.display(description="Requested", ordering="amount_requested")
    def requested(self, obj):
        return _naira(obj.amount_requested)

    @admin.display(description="To loan")
    def deduction(self, obj):
        if not obj.loan_deduction:
            return "None"
        return pill(f"-{_naira(obj.loan_deduction)}", "wait")

    @admin.display(description="Pay out", ordering="net_amount")
    def net(self, obj):
        return format_html("<strong>{}</strong>", _naira(obj.net_amount))

    @admin.display(description="Destination")
    def destination(self, obj):
        # The account on file when the payout was requested, not today's.
        if obj.paid_to:
            return obj.paid_to
        agent = obj.agent
        return f"{agent.bank_name} · {agent.account_number} ({agent.account_name})"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = {
            Withdrawal.Status.PAID: "ok",
            Withdrawal.Status.FAILED: "bad",
            Withdrawal.Status.PENDING: "wait",
        }.get(obj.status, "idle")
        return _pill(obj.get_status_display(), tone)

    @admin.action(description="Mark as paid out")
    def action_mark_paid(self, request, queryset):
        pending = list(queryset.filter(status=Withdrawal.Status.PENDING).select_related("agent__user"))
        # Still pending at the moment of writing: one failed by someone else in
        # between is not turned into a payout.
        count = Withdrawal.objects.filter(
            pk__in=[w.pk for w in pending], status=Withdrawal.Status.PENDING
        ).update(status=Withdrawal.Status.PAID)
        paid = set(
            Withdrawal.objects.filter(pk__in=[w.pk for w in pending], status=Withdrawal.Status.PAID)
            .values_list("pk", flat=True)
        )
        for withdrawal in (w for w in pending if w.pk in paid):
            send_agent_payout_sent_email(withdrawal)
        self.message_user(request, f"{_plural(count, 'payout')} marked as sent.", messages.SUCCESS)

    @admin.action(description="Mark as failed and refund the balance")
    @transaction.atomic
    def action_mark_failed(self, request, queryset):
        count = 0
        # Locked and re-read, so a payout marked paid or failed by someone else
        # in the meantime is not refunded a second time.
        for withdrawal in queryset.select_for_update().filter(status=Withdrawal.Status.PENDING):
            withdrawal.status = Withdrawal.Status.FAILED
            withdrawal.save(update_fields=["status"])

            # A payout that never left the bank has to be given back, including
            # the slice that was applied to the agent's loan.
            wallet = Wallet.objects.select_for_update().get(agent_id=withdrawal.agent_id)
            wallet.total_withdrawn = max(
                Decimal("0.00"), wallet.total_withdrawn - withdrawal.amount_requested
            )
            wallet.loan_balance += withdrawal.loan_deduction
            wallet.save(update_fields=["total_withdrawn", "loan_balance"])
            count += 1
            transaction.on_commit(
                lambda withdrawal=withdrawal: send_agent_payout_failed_email(withdrawal)
            )

        self.message_user(
            request,
            f"{_plural(count, 'payout')} failed and the balance returned to the agent.",
            messages.WARNING,
        )



# Supervisor screens are registered by importing their module.
from . import supervisor_admin  # noqa: E402,F401  isort:skip
