"""Partner operations: approving ads funding and releasing payouts.

Both actions move real money, so both are deliberate: a loan is approved and
disbursed in one reviewed step that credits the agent's loan balance, and a
withdrawal is only marked paid once it has actually left the account.
"""

from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import format_html

from apps.accounts.deletion import AccountDeleteMixin
from apps.accounts.testdata import RealDataOnlyAdmin
from config.admin_ui import pill

from .payout_admin import PaystackPayoutActions

from apps.accounts.emails import (
    send_agent_payout_failed_email,
    send_agent_payout_sent_email,
    send_loan_approved_email,
    send_loan_declined_email,
    send_partnership_certificate_email,
)

from .models import AgentContract, AgentProfile, Commission, Loan, Wallet, Withdrawal


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


class AgentContractForm(forms.ModelForm):
    """Upload a paper contract the agent signed before the portal had one."""

    class Meta:
        model = AgentContract
        fields = ("file", "signed_on")

    def clean_file(self):
        from rest_framework.exceptions import ValidationError as UploadRejected

        from apps.applications.uploads import validate_upload

        upload = self.cleaned_data.get("file")
        if upload and hasattr(upload, "content_type"):
            try:
                validate_upload(upload, max_mb=15)
            except UploadRejected as error:
                raise forms.ValidationError(" ".join(str(item) for item in error.detail))
        return upload

    def save(self, commit=True):
        contract = super().save(commit=False)
        if "file" in self.changed_data and contract.file:
            contract.source = AgentContract.Source.UPLOADED
        if commit:
            contract.save()
        return contract


class AgentContractInline(admin.StackedInline):
    """The agent's partnership contract.

    A contract signed in the portal is read-only here. For an agent who signed
    on paper before the portal had a contract page, upload the signed copy
    (PDF or image) and its date; it then appears on their Contract page.
    """

    model = AgentContract
    form = AgentContractForm
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name = "partnership contract"
    verbose_name_plural = "partnership contract"
    readonly_fields = ("source", "signer_name", "signature_method", "signed_at", "emailed_at")

    def get_fields(self, request, obj=None):
        return ("file", "signed_on") + self.readonly_fields

    def get_readonly_fields(self, request, obj=None):
        contract = getattr(obj, "contract", None) if obj else None
        if contract is not None and contract.source == AgentContract.Source.PORTAL and contract.file:
            return ("file", "signed_on") + self.readonly_fields
        return self.readonly_fields


@admin.register(AgentProfile)
class AgentProfileAdmin(AccountDeleteMixin, RealDataOnlyAdmin, admin.ModelAdmin):
    test_user_paths = ("user",)

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
        "contract_link",
        "created_at",
    )
    search_fields = ("user__full_name", "user__email", "agency_name", "account_number")
    list_filter = ("supervisor",)
    autocomplete_fields = ("user", "supervisor")
    readonly_fields = ("partner_code", "certificate_link", "contract_link", "account_verified_at", "created_at")
    inlines = (AgentContractInline, WalletInline, CommissionInline)
    actions = ("action_send_partnership_certificate", "action_send_custom_message")

    fieldsets = (
        (None, {"fields": ("user", "partner_code", "agency_name", "address", "supervisor", "certificate_link", "contract_link", "contract_required", "total_closed_sales", "created_at")}),
        ("Payout account", {"fields": ("bank_name", "account_number", "account_name", "bank_code", "account_verified_at")}),
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
            path(
                "<int:agent_id>/contract/",
                self.admin_site.admin_view(self.download_contract_view),
                name="agent-contract-download",
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

    def download_contract_view(self, request, agent_id):
        from django.http import Http404, HttpResponse

        contract = AgentContract.objects.select_related("agent").filter(agent_id=agent_id).first()
        if contract is None or not contract.file:
            raise Http404("This agent has no contract on file.")
        with contract.file.open("rb") as handle:
            data = handle.read()
        response = HttpResponse(data, content_type=contract.content_type)
        response["Content-Disposition"] = f'inline; filename="{contract.filename}"'
        return response

    @admin.display(description="Contract")
    def contract_link(self, obj):
        from django.urls import reverse

        if not obj or not obj.pk:
            return "—"
        status = obj.contract_status
        if status == "signed":
            url = reverse("admin:agent-contract-download", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" target="_blank" rel="noopener noreferrer" style="white-space:nowrap; padding: 3px 8px; font-size: 11px;">View PDF</a>',
                url,
            )
        if status == "pending":
            return _pill("Not signed yet", "wait")
        return "—"

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
        count = obj.applications.count()
        if not count:
            return "0"
        from django.urls import reverse
        url = reverse("admin:applications_agentapplication_changelist") + f"?agent={obj.pk}"
        return format_html('<a href="{}"><strong>{}</strong></a>', url, count)

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

    @admin.action(description="Send custom message (with attachment)")
    def action_send_custom_message(self, request, queryset):
        """Send a custom message with optional attachments to the selected partner agents."""
        from apps.accounts.emails import extract_attachments, send_custom_message_email
        from django.http import HttpResponseRedirect
        from django.shortcuts import render
        from django.urls import reverse

        if request.POST.get("apply") == "send_custom_message":
            # Read PKs embedded by intermediate template, or fallback to queryset
            from apps.accounts.models import User
            selected_pks = request.POST.getlist("_selected_action")
            if selected_pks:
                users = list(
                    User.objects.filter(pk__in=selected_pks)
                    .exclude(email="")
                    .exclude(email__isnull=True)
                )
            else:
                users = [agent.user for agent in queryset.select_related("user") if agent.user and agent.user.email]
            if not users:
                self.message_user(request, "No valid recipients found. Please go back and try again.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            subject = request.POST.get("subject", "").strip()
            message_body = request.POST.get("message", "").strip()
            if not subject or not message_body:
                self.message_user(request, "Subject and message are both required.", messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            attachments = extract_attachments(request)
            sent_count = 0
            failed_count = 0

            for user in users:
                if send_custom_message_email(user, subject, message_body, attachments=attachments, wait=True):
                    sent_count += 1
                else:
                    failed_count += 1

            att_info = f" with {len(attachments)} attachment(s)" if attachments else ""
            if sent_count:
                self.message_user(
                    request,
                    f"Custom message{att_info} emailed to {sent_count} agent(s).",
                    messages.SUCCESS,
                )
            if failed_count:
                self.message_user(
                    request,
                    f"Failed to email {failed_count} agent(s). Check mail server logs.",
                    messages.ERROR,
                )
            return HttpResponseRedirect(reverse("admin:partners_agentprofile_changelist"))

        # First step: show intermediate form with the selected agents from queryset
        users = [agent.user for agent in queryset.select_related("user") if agent.user and agent.user.email]
        if not users:
            self.message_user(request, "None of the selected agents have a valid email address.", messages.WARNING)
            return None

        return render(
            request,
            "admin/accounts/send_custom_message_intermediate.html",
            {
                "title": "Send custom message to partner agents",
                "recipients": users,
                "action_name": "action_send_custom_message",
                "back_url": reverse("admin:partners_agentprofile_changelist"),
            },
        )


def locked_loans(queryset):
    """The selected loans, locked for this transaction.

    The admin's list query also loads each agent's wallet with an outer join,
    and PostgreSQL refuses to lock rows from a query like that ("FOR UPDATE
    cannot be applied to the nullable side of an outer join"). Every approval
    failed with a server error on the live database, while SQLite, which the
    tests use, ignores locking and let it through. So the loans are locked on
    their own, without the joins.
    """
    return Loan.objects.select_for_update().filter(pk__in=list(queryset.values_list("pk", flat=True)))


@admin.register(Loan)
class LoanAdmin(RealDataOnlyAdmin, admin.ModelAdmin):
    """Ads funding requests waiting on a decision."""

    test_user_paths = ("agent__user",)

    list_display = ("reference", "agent", "requested", "purpose", "campaign", "meta_account", "status_badge", "requested_at")
    list_filter = ("status", "purpose", "requested_at")
    search_fields = ("agent__user__full_name", "agent__user__email", "purpose")
    autocomplete_fields = ("agent",)
    date_hierarchy = "requested_at"
    # Status moves only through the actions, which also move the agent's loan
    # balance. Set by hand it changed the status and left the balance behind.
    readonly_fields = (
        "reference", "status", "currency", "requested_at", "disbursed_at", "campaign",
        "meta_account", "invoice_expires_at", "paystack_reference", "transfer_code",
        "review_reason", "failure_reason", "approved_by", "sent_at",
    )
    actions = (
        "action_approve_and_pay_meta",
        "action_check_paystack",
        "action_approve_and_disburse",
        "action_mark_repaid",
        "action_decline",
    )

    def has_delete_permission(self, request, obj=None):
        """Funding that was paid out or repaid is a record of money and stays.
        A request still in review, or declined, may be removed."""
        if obj is not None and obj.status in (Loan.Status.APPROVED, Loan.Status.DISBURSED, Loan.Status.REPAID):
            return False
        return super().has_delete_permission(request, obj)

    fieldsets = (
        (None, {"fields": ("reference", "agent", "status", "currency")}),
        ("Request", {"fields": ("requested_amount", "purpose", "ad_account_link", "campaign")}),
        ("Meta invoice (paid through Paystack)", {"fields": ("meta_account", "invoice_expires_at")}),
        ("Disbursement", {"fields": (
            "approved_amount", "requested_at", "disbursed_at", "approved_by", "sent_at",
            "paystack_reference", "transfer_code", "review_reason", "failure_reason",
        )}),
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
            Loan.Status.FAILED: "bad",
            Loan.Status.PENDING: "wait",
            Loan.Status.SENDING: "info",
        }.get(obj.status, "idle")
        return _pill(obj.get_status_display(), tone)

    @admin.display(description="Meta invoice account")
    def meta_account(self, obj):
        if obj.awaiting_invoice and not obj.pays_meta:
            return "Waiting for the agent to give the invoice and pay"
        if not obj.pays_meta:
            return "None (paid by staff)"
        expiry = f", expires {timezone.localtime(obj.invoice_expires_at):%d %b %H:%M}" if obj.invoice_expires_at else ""
        return f"{obj.meta_account_name} · {obj.meta_bank_name or obj.meta_bank_code} · {obj.meta_account_number}{expiry}"

    @admin.action(description="Approve for Meta (the agent then gives the invoice and pays)")
    def action_approve_and_pay_meta(self, request, queryset):
        """Approve requests from agents paid through a Meta invoice. Nothing else.

        Nothing is paid here: the agent is emailed, gives the Meta invoice on
        the dashboard and presses Pay. An older request that already carries
        an invoice is paid as before.
        """
        from .loan_payouts import approve_and_send, approve_for_invoice, meta_invoice_offered

        approved = paid = held = skipped = 0
        for loan in queryset.filter(status=Loan.Status.PENDING).select_related("agent__user", "agent__wallet"):
            if loan.pays_meta:
                result = approve_and_send(loan, request.user)
                if result.status in (Loan.Status.DISBURSED, Loan.Status.SENDING):
                    paid += 1
                else:
                    held += 1
                    self.message_user(
                        request,
                        f"{result.reference} not paid: {result.review_reason or result.failure_reason or 'see the request'}",
                        messages.WARNING,
                    )
                continue
            if not meta_invoice_offered(loan.agent):
                skipped += 1
                continue
            if approve_for_invoice(loan, request.user).status == Loan.Status.APPROVED:
                approved += 1
        if approved:
            self.message_user(
                request,
                f"{_plural(approved, 'loan')} approved. The agent was emailed to give the Meta invoice and pay it.",
                messages.SUCCESS,
            )
        if paid:
            self.message_user(request, f"{_plural(paid, 'loan')} paid to Meta.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"{_plural(skipped, 'loan')} skipped: not an agent paid through a Meta invoice (use Approve and disburse).",
                messages.WARNING,
            )
        if not (approved or paid or held or skipped):
            self.message_user(request, "Nothing to approve: choose requests that are in review.", messages.INFO)

    @admin.action(description="Check with Paystack")
    def action_check_paystack(self, request, queryset):
        from .loan_payouts import check

        checked = 0
        for loan in queryset.filter(status=Loan.Status.SENDING):
            check(loan)
            checked += 1
        self.message_user(request, f"{_plural(checked, 'loan')} checked with Paystack.", messages.INFO)

    @admin.action(description="Approve and disburse (paid by staff, no Meta invoice)")
    @transaction.atomic
    def action_approve_and_disburse(self, request, queryset):
        released = Decimal("0")
        count = 0
        # Locked, so two staff approving at once cannot release a loan twice.
        loans = locked_loans(queryset).exclude(
            status__in=(Loan.Status.DISBURSED, Loan.Status.REPAID, Loan.Status.SENDING, Loan.Status.FAILED)
        ).filter(meta_account_number="", paystack_reference=None)
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
        for loan in locked_loans(queryset).filter(status=Loan.Status.DISBURSED):
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
class WithdrawalAdmin(PaystackPayoutActions, RealDataOnlyAdmin, admin.ModelAdmin):
    """Payouts waiting to be sent to an agent's bank account."""

    test_user_paths = ("agent__user",)

    list_display = (
        "reference",
        "agent",
        "requested",
        "deduction",
        "net",
        "destination",
        "method_label",
        "status_badge",
        "note",
        "created_at",
    )
    list_filter = ("status", "method", "created_at")
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
        "method",
        "paystack_reference",
        "transfer_code",
        "review_reason",
        "failure_reason",
        "approved_by",
        "sent_at",
        "paid_at",
        "created_at",
    )
    actions = ("action_approve_and_send", "action_check_paystack", "action_mark_paid", "action_mark_failed")

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

    @admin.action(description="Mark as paid out (paid by staff)")
    def action_mark_paid(self, request, queryset):
        """For payouts staff paid themselves. A Paystack payout is marked paid
        by Paystack, so only payouts in review can be marked here."""
        from django.utils import timezone

        pending = self.cleared_by_paystack(
            request, queryset.filter(status=Withdrawal.Status.PENDING).select_related("agent__user")
        )
        # Still pending at the moment of writing: one failed by someone else in
        # between is not turned into a payout.
        count = Withdrawal.objects.filter(
            pk__in=[w.pk for w in pending], status=Withdrawal.Status.PENDING
        ).update(status=Withdrawal.Status.PAID, method=Withdrawal.Method.MANUAL, paid_at=timezone.now())
        paid = set(
            Withdrawal.objects.filter(pk__in=[w.pk for w in pending], status=Withdrawal.Status.PAID)
            .values_list("pk", flat=True)
        )
        for withdrawal in (w for w in pending if w.pk in paid):
            send_agent_payout_sent_email(withdrawal)
        self.message_user(request, f"{_plural(count, 'payout')} marked as sent.", messages.SUCCESS)

    @admin.action(description="Mark as failed and refund the balance")
    def action_mark_failed(self, request, queryset):
        """Give the money back for payouts in review. A payout that is Sending
        may already be on its way, so it is checked with Paystack instead."""
        count = 0
        pending = self.cleared_by_paystack(request, queryset.filter(status=Withdrawal.Status.PENDING))
        for withdrawal in pending:
            # Only if still in review now: it may have been sent meanwhile.
            if withdrawal.refund_if_pending("Marked as failed by staff."):
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
