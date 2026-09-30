from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from config.admin_ui import button_link, pill, plural

from apps.applications import services

from .models import Payment, PaymentToConfirm
from .settlement import settle


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Application fees, and the two manual overrides staff occasionally need:
    confirming a transfer that arrived off-platform, and waiving a fee."""

    list_display = (
        "reference",
        "application",
        "status_badge",
        "charged",
        "in_naira",
        "gateway",
        "paid_at",
    )
    list_filter = ("status", "gateway", "currency", "paid_at")
    search_fields = ("reference", "application__reference", "application__full_name")
    autocomplete_fields = ("application",)
    date_hierarchy = "created_at"
    readonly_fields = ("reference", "created_at", "paid_at", "charged", "in_naira")
    # Confirming a transfer is done on "Payments to confirm", its own screen.
    actions = ("action_waive",)

    fieldsets = (
        (None, {"fields": ("reference", "application", "status", "gateway")}),
        ("Charged", {"fields": ("currency", "symbol", "amount", "processing_fee", "charged")}),
        ("Reconciliation", {"fields": ("amount_ngn", "fx_rate", "in_naira", "created_at", "paid_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("application")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tones = {Payment.Status.PAID: "ok", Payment.Status.WAIVED: "info", Payment.Status.FAILED: "bad"}
        return pill(obj.get_status_display(), tones.get(obj.status, "wait"))

    @admin.display(description="Total")
    def charged(self, obj):
        return obj.display_total

    @admin.display(description="In Naira", ordering="amount_ngn")
    def in_naira(self, obj):
        return f"₦{obj.amount_ngn:,.2f}"

    @admin.action(description="Waive the fee")
    def action_waive(self, request, queryset):
        count = 0
        for payment in queryset.exclude(status=Payment.Status.WAIVED):
            payment.mark_waived()
            services.notify(
                payment.application, "Your application fee has been waived."
            )
            count += 1
        self.message_user(request, f"{count} fee(s) waived.", messages.SUCCESS)



class RejectReceiptForm(forms.Form):
    note = forms.CharField(
        label="Why can this transfer not be confirmed?",
        widget=forms.Textarea(attrs={"rows": 4, "cols": 70}),
        max_length=1000,
        help_text="Emailed word for word to whoever sent the receipt.",
    )


@admin.register(PaymentToConfirm)
class PaymentToConfirmAdmin(admin.ModelAdmin):
    """Bank transfers waiting for the money to be checked.

    Confirm pays the agent's commission. Reject sends the payer your reason and
    lets them upload a new receipt.
    """

    list_display = ("reference", "student", "filed_by", "amount_due", "transfer_bank", "submitted", "open_link")
    search_fields = ("reference", "application__reference", "application__full_name")
    list_display_links = ("reference",)
    actions = ("action_confirm",)
    change_form_template = "admin/payments/paymenttoconfirm/review.html"
    readonly_fields = ("reference", "student", "filed_by", "amount_due", "transfer_bank", "submitted", "gateway")
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(status=Payment.Status.REVIEW)
            .select_related("application", "application__submitted_by_agent__user")
            .order_by("receipt_submitted_at")
        )

    @admin.display(description="Student", ordering="application__full_name")
    def student(self, obj):
        return f"{obj.application.full_name} · {obj.application.reference}"

    @admin.display(description="Filed by")
    def filed_by(self, obj):
        agent = obj.application.submitted_by_agent
        return (agent.user.full_name or agent.user.email) if agent else "The applicant"

    @admin.display(description="Amount", ordering="amount_ngn")
    def amount_due(self, obj):
        return f"{obj.display_total} (₦{obj.total_ngn:,.2f})"

    @admin.display(description="Receipt sent", ordering="receipt_submitted_at")
    def submitted(self, obj):
        return obj.receipt_submitted_at

    @admin.display(description="")
    def open_link(self, obj):
        return button_link(reverse("admin:payments_paymenttoconfirm_change", args=[obj.pk]), "Review", primary=True)

    def get_urls(self):
        return [
            path("<int:pk>/confirm/", self.admin_site.admin_view(self.confirm_view), name="payments_paymenttoconfirm_confirm"),
            path("<int:pk>/reject/", self.admin_site.admin_view(self.reject_view), name="payments_paymenttoconfirm_reject"),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        payment = Payment.objects.filter(pk=object_id).first()
        if payment is None or payment.status != Payment.Status.REVIEW:
            self.message_user(request, "That payment is no longer waiting for confirmation.", messages.INFO)
            return HttpResponseRedirect(reverse("admin:payments_paymenttoconfirm_changelist"))
        name = (payment.receipt.name if payment.receipt else "").lower()
        extra_context = {
            **(extra_context or {}),
            "title": "Confirm a bank transfer",
            "payment": payment,
            "file_url": payment.receipt.url if payment.receipt else "",
            "is_pdf": name.endswith(".pdf"),
            "is_image": name.endswith((".jpg", ".jpeg", ".png", ".webp")),
            "confirm_url": reverse("admin:payments_paymenttoconfirm_confirm", args=[payment.pk]),
            "reject_url": reverse("admin:payments_paymenttoconfirm_reject", args=[payment.pk]),
            "show_save": False,
            "show_save_and_continue": False,
            "show_save_and_add_another": False,
            "show_delete": False,
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def _confirm(self, payment):
        """Settle one transfer. Returns the commission credited, or None if it was not waiting."""
        if payment.status != Payment.Status.REVIEW:
            return None
        before = sum(c.amount for c in payment.application.commissions.all())
        settle(payment, Payment.Gateway.TRANSFER)
        after = sum(c.amount for c in payment.application.commissions.all())
        return after - before

    def confirm_view(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        if request.method == "POST":
            credited = self._confirm(payment)
            if credited is None:
                self.message_user(request, "That payment was already handled.", messages.INFO)
            else:
                self.message_user(
                    request,
                    f"Payment {payment.reference} confirmed."
                    + (f" ₦{credited:,.0f} commission credited to the agent." if credited else ""),
                    messages.SUCCESS,
                )
        return HttpResponseRedirect(reverse("admin:payments_paymenttoconfirm_changelist"))

    def reject_view(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, status=Payment.Status.REVIEW)
        form = RejectReceiptForm(request.POST or None)
        back = reverse("admin:payments_paymenttoconfirm_change", args=[payment.pk])
        if request.method == "POST" and form.is_valid():
            services.reject_transfer(payment, form.cleaned_data["note"])
            self.message_user(request, f"Receipt for {payment.reference} rejected and the reason emailed.", messages.WARNING)
            return HttpResponseRedirect(reverse("admin:payments_paymenttoconfirm_changelist"))
        return render(
            request,
            "admin/payments/paymenttoconfirm/reject.html",
            {**self.admin_site.each_context(request), "title": "Reject a transfer receipt", "payment": payment,
             "form": form, "opts": self.model._meta, "back_url": back},
        )

    @admin.action(description="Confirm payment received (credits the agent)")
    def action_confirm(self, request, queryset):
        confirmed = credited = 0
        for payment in queryset:
            amount = self._confirm(payment)
            if amount is not None:
                confirmed += 1
                credited += amount
        self.message_user(
            request,
            f"{plural(confirmed, 'payment')} confirmed."
            + (f" ₦{credited:,.0f} commission credited to partner agents." if credited else ""),
            messages.SUCCESS,
        )
