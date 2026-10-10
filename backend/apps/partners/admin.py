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
    send_partnership_certificate_email,
)

from .models import AgentProfile, Commission, Loan, Wallet, Withdrawal


def _plural(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _naira(value):
    return f"₦{Decimal(value or 0):,.0f}"


def _money(value, currency):
    """An agent's amount in the currency it is held in."""
    from .currency import money

    return money(Decimal(value or 0), currency)


def _pill(text, tone):
    return pill(text, tone)


class WalletInline(admin.StackedInline):
    model = Wallet
    can_delete = False
    # Read-only: the totals are moved by commissions, payouts and Ads funding,
    # each of which leaves a dated record. A total typed in by hand would not
    # match the agent's earning history.
    readonly_fields = (
        "registration_commission_total",
        "visa_commission_total",
        "total_earned",
        "available",
        "loan_balance",
        "loan_repaid_total",
        "saved_balance",
        "total_withdrawn",
        "currency",
        "updated_at",
    )
    fields = (
        ("registration_commission_total", "visa_commission_total"),
        ("total_earned", "available"),
        ("loan_balance", "loan_repaid_total"),
        ("saved_balance", "total_withdrawn"),
        ("currency", "updated_at"),
    )

    @admin.display(description="Available to withdraw")
    def available(self, obj):
        return _money(obj.available_balance, obj.currency)


class CommissionInline(admin.TabularInline):
    model = Commission
    extra = 0
    can_delete = False
    fields = ("application", "kind", "amount", "currency", "amount_ngn", "fx_rate", "earned_at")
    readonly_fields = fields
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
        "certificate_link",
        "created_at",
    )
    search_fields = ("user__full_name", "user__email", "agency_name", "account_number")
    list_filter = ("supervisor",)
    autocomplete_fields = ("user", "supervisor")
    readonly_fields = ("partner_code", "certificate_link", "created_at")
    inlines = (WalletInline, CommissionInline)
    actions = ("action_send_partnership_certificate",)

    fieldsets = (
        (None, {"fields": ("user", "partner_code", "agency_name", "supervisor", "certificate_link", "total_closed_sales", "created_at")}),
        ("Payout account", {"fields": ("bank_name", "account_number", "account_name")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "wallet", "supervisor__user")

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:agent_id>/certificate/",
                self.admin_site.admin_view(self.download_certificate_view),
                name="agent-certificate-download",
            ),
        ]
        return custom_urls + urls

    def download_certificate_view(self, request, agent_id):
        from django.http import Http404, HttpResponse
        from apps.partners.certificate import build_partnership_certificate

        agent = self.get_object(request, agent_id)
        if not agent:
            raise Http404("Agent profile not found")
        pdf_bytes = build_partnership_certificate(agent)
        name = agent.user.full_name or agent.agency_name or f"agent_{agent.id}"
        safe_name = "".join(c if c.isalnum() else "_" for c in name).strip("_")
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="Apply_Gabstep_Certificate_{safe_name}.pdf"'
        return response

    @admin.display(description="Certificate")
    def certificate_link(self, obj):
        from django.urls import reverse
        if not obj or not obj.pk:
            return "—"
        url = reverse("admin:agent-certificate-download", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener noreferrer" style="white-space:nowrap; padding: 3px 8px; font-size: 11px;">View PDF</a>',
            url,
        )

    @admin.display(description="Students")
    def students(self, obj):
        return obj.applications.count()

    @admin.display(description="Earned")
    def earned(self, obj):
        return _money(obj.wallet.total_earned, obj.wallet.currency)

    @admin.display(description="Loan owed")
    def owing(self, obj):
        balance = obj.wallet.loan_balance
        return _pill(_money(balance, obj.wallet.currency), "wait" if balance else "idle")

    @admin.action(description="Send partnership certificate by email")
    def action_send_partnership_certificate(self, request, queryset):
        """Queue a certificate email for every selected agent.

        Each email is dispatched on a background daemon thread (matching the
        pattern used throughout this project) so the admin page responds
        immediately even when many agents are selected.
        """
        sent = 0
        agents = queryset.select_related("user")
        for agent in agents:
            if not agent.user.email:
                self.message_user(
                    request,
                    f"Skipped {agent} – no email address on file.",
                    messages.WARNING,
                )
                continue
            send_partnership_certificate_email(agent)
            sent += 1

        if sent:
            self.message_user(
                request,
                f"Partnership certificate queued for {_plural(sent, 'agent')}. "
                "The email will arrive shortly.",
                messages.SUCCESS,
            )


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    """Ads funding requests waiting on a decision."""

    list_display = ("reference", "agent", "requested", "purpose", "campaign", "status_badge", "requested_at")
    list_filter = ("status", "purpose", "requested_at")
    search_fields = ("agent__user__full_name", "agent__user__email", "purpose")
    autocomplete_fields = ("agent",)
    date_hierarchy = "requested_at"
    # Status moves only through the actions, which also move the agent's loan
    # balance. Set by hand it changed the status and left the balance behind.
    readonly_fields = ("reference", "status", "currency", "requested_at", "disbursed_at", "campaign")
    actions = ("action_approve_and_disburse", "action_mark_repaid", "action_decline")

    def has_delete_permission(self, request, obj=None):
        """Funding that was paid out or repaid is a record of money and stays.
        A request still in review, or declined, may be removed."""
        if obj is not None and obj.status in (Loan.Status.APPROVED, Loan.Status.DISBURSED, Loan.Status.REPAID):
            return False
        return super().has_delete_permission(request, obj)

    fieldsets = (
        (None, {"fields": ("reference", "agent", "status", "currency")}),
        ("Request", {"fields": ("requested_amount", "purpose", "ad_account_link", "campaign")}),
        ("Disbursement", {"fields": ("approved_amount", "requested_at", "disbursed_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("agent__user", "agent__wallet")

    @admin.display(description="Requested", ordering="requested_amount")
    def requested(self, obj):
        return _money(obj.requested_amount, obj.currency)

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
        released_by_currency = {}
        for loan in loans:
            loan.status = Loan.Status.DISBURSED
            loan.approved_amount = loan.requested_amount
            loan.disbursed_at = timezone.now()
            loan.save()

            # Added in the database, so a withdrawal made at the same moment is
            # not overwritten by this copy of the wallet. The loan was asked for
            # in the wallet's currency; an empty wallet takes the loan's, so the
            # balance is never added in two currencies.
            wallet, _ = Wallet.objects.get_or_create(agent=loan.agent)
            if wallet.is_empty and wallet.currency != loan.currency:
                Wallet.objects.filter(pk=wallet.pk).update(currency=loan.currency)
            Wallet.objects.filter(agent=loan.agent).update(
                loan_balance=F("loan_balance") + loan.approved_amount
            )

            released_by_currency[loan.currency] = (
                released_by_currency.get(loan.currency, Decimal("0")) + loan.approved_amount
            )
            released += loan.approved_amount
            count += 1
            # Queued after the write so the agent is only told about money that
            # is actually in their balance.
            transaction.on_commit(lambda loan=loan: send_loan_approved_email(loan))

        self.message_user(
            request,
            f"{_plural(count, 'loan')} disbursed"
            + (", " + " and ".join(_money(total, cur) for cur, total in released_by_currency.items()) + " released."
               if released_by_currency else "."),
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
        "currency",
        "destination",
        # Moved only by the actions below. Editing it by hand could turn a paid
        # payout back to pending and then refund it.
        "status",
        "created_at",
    )
    actions = ("action_mark_paid", "action_mark_failed")

    # A payout is raised by the agent and moved by the actions. The balance moved
    # when it was raised, so deleting one, even a pending one, would lose that
    # money from the agent's history without giving it back: "Mark as failed"
    # is what returns it.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("agent__user")

    @admin.display(description="Requested", ordering="amount_requested")
    def requested(self, obj):
        return _money(obj.amount_requested, obj.currency)

    @admin.display(description="To loan")
    def deduction(self, obj):
        if not obj.loan_deduction:
            return "None"
        return pill(f"-{_money(obj.loan_deduction, obj.currency)}", "wait")

    @admin.display(description="Pay out", ordering="net_amount")
    def net(self, obj):
        return format_html("<strong>{}</strong>", _money(obj.net_amount, obj.currency))

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
