from django.contrib import admin, messages
from django.utils.html import format_html

from apps.applications import services

from .models import Payment
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
    actions = ("action_mark_paid", "action_waive")

    fieldsets = (
        (None, {"fields": ("reference", "application", "status", "gateway")}),
        ("Charged", {"fields": ("currency", "symbol", "amount", "processing_fee", "charged")}),
        ("Reconciliation", {"fields": ("amount_ngn", "fx_rate", "in_naira", "created_at", "paid_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("application")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colours = {
            Payment.Status.PAID: ("#dcfce7", "#166534"),
            Payment.Status.WAIVED: ("#e0e7ff", "#3730a3"),
            Payment.Status.FAILED: ("#fee2e2", "#991b1b"),
        }
        background, colour = colours.get(obj.status, ("#fef3c7", "#92400e"))
        return format_html(
            '<span style="display:inline-block;padding:2px 9px;border-radius:999px;'
            'background:{};color:{};font-size:11px;font-weight:700">{}</span>',
            background,
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Total")
    def charged(self, obj):
        return obj.display_total

    @admin.display(description="In Naira", ordering="amount_ngn")
    def in_naira(self, obj):
        return f"₦{obj.amount_ngn:,.2f}"

    @admin.action(description="Confirm payment received (pays the agent)")
    def action_mark_paid(self, request, queryset):
        count = 0
        credited = 0
        for payment in queryset.exclude(status=Payment.Status.PAID):
            # The same settlement path the webhook uses, so a transfer confirmed
            # by hand and a card paid online cannot end up meaning different
            # things. It is idempotent, so a double click is harmless.
            before = payment.application.commissions.count()
            if settle(payment, Payment.Gateway.PARTNER):
                count += 1
                payment.application.refresh_from_db()
                for commission in payment.application.commissions.all()[before:]:
                    credited += commission.amount
        self.message_user(
            request,
            f"{count} payment(s) confirmed."
            + (f" ₦{credited:,.0f} commission paid to partner agents." if credited else ""),
            messages.SUCCESS,
        )

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
