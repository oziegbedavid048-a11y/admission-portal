"""Creating and overseeing sales managers from the admissions desk.

A sales manager is a user plus a profile, and asking staff to make the user
first and remember to come back is how half-made accounts happen, so both are
created on one screen. Saving generates the agent code that ties agents to them.
"""

from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html

from apps.accounts.emails import (
    send_manager_payout_failed_email,
    send_manager_payout_sent_email,
    send_sales_manager_welcome_email,
)
from apps.accounts.models import User

from .models import (
    AgentProfile,
    SupervisorBonus,
    SupervisorProfile,
    SupervisorWithdrawal,
)


def _naira(value):
    return f"₦{Decimal(value or 0):,.0f}"


class SupervisorProfileForm(forms.ModelForm):
    """The sign-in and the profile, filled in together."""

    email = forms.EmailField(
        label="Email address", help_text="What the sales manager signs in with."
    )
    full_name = forms.CharField(label="Full name", max_length=180)
    phone = forms.CharField(label="Phone", max_length=40, required=False)
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Leave blank to keep the current password. At least 8 characters.",
    )

    class Meta:
        model = SupervisorProfile
        fields = ("region", "bank_name", "account_number", "account_name", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields["email"].initial = user.email
            self.fields["full_name"].initial = user.full_name
            self.fields["phone"].initial = user.phone
        else:
            self.fields["password"].required = True
            self.fields["password"].help_text = "At least 8 characters."

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        clash = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.user_id)
        if clash.exists():
            raise ValidationError("Another account already uses this email address.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password)
        return password

    def clean_account_number(self):
        number = (self.cleaned_data.get("account_number") or "").strip()
        if number and not (number.isdigit() and len(number) == 10):
            raise ValidationError("Account number should be 10 digits.")
        return number

    def save(self, commit=True):
        profile = super().save(commit=False)
        data = self.cleaned_data
        is_new = profile.pk is None

        user = profile.user if profile.pk else User(role=User.Role.SUPERVISOR)
        user.email = data["email"]
        user.full_name = data["full_name"]
        user.phone = data.get("phone", "")
        user.role = User.Role.SUPERVISOR
        user.is_active = True
        if data.get("password"):
            user.set_password(data["password"])
        user.save()

        profile.user = user
        if commit:
            profile.save()
            if is_new:
                # A sales manager never signs themselves up, so this is the only
                # way they learn the account exists and what their code is. The
                # code is only on the profile once it has been saved.
                send_sales_manager_welcome_email(
                    user, profile, password=data.get("password")
                )
        return profile


class SupervisedAgentInline(admin.TabularInline):
    """Who is on this sales manager's team.

    Read-only on purpose: an agent joins by entering the code at sign-up, not by
    being dropped in here, so the list always reflects what actually happened.
    """

    model = AgentProfile
    fk_name = "supervisor"
    extra = 0
    can_delete = False
    max_num = 0
    fields = ("user", "agency_name", "bank_name", "total_closed_sales", "created_at")
    readonly_fields = fields


class SupervisorBonusInline(admin.TabularInline):
    model = SupervisorBonus
    fk_name = "supervisor"
    extra = 0
    can_delete = False
    max_num = 0
    fields = ("application", "agent", "amount", "earned_at")
    readonly_fields = fields
    ordering = ("-earned_at",)


@admin.register(SupervisorProfile)
class SupervisorProfileAdmin(admin.ModelAdmin):
    """Create a sales manager here, then hand them the agent code it generates.

    That code is what ties agents to them: an agent types it into the sign-up
    form, and from that point the sales manager sees the agent and every student
    they register, and earns a bonus on each of those registrations.
    """

    form = SupervisorProfileForm
    list_display = (
        "code_badge",
        "name",
        "email_address",
        "region",
        "team",
        "verified",
        "earned",
        "is_active",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("user__full_name", "user__email", "agent_code", "region")
    readonly_fields = (
        "agent_code_display",
        "bonus_total",
        "total_withdrawn",
        "available",
        "created_at",
    )
    inlines = (SupervisedAgentInline, SupervisorBonusInline)

    fieldsets = (
        ("Sign-in", {"fields": ("full_name", "email", "phone", "password")}),
        (
            "Agent code",
            {
                "fields": ("agent_code_display", "is_active"),
                "description": (
                    "Generated automatically when you save. Give this code to the "
                    "agents who report to this sales manager; they enter it on the "
                    "agent sign-up form."
                ),
            },
        ),
        ("Team", {"fields": ("region",)}),
        ("Payout account", {"fields": ("bank_name", "account_number", "account_name")}),
        (
            "Earnings",
            {"fields": ("bonus_total", "total_withdrawn", "available", "created_at")},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="Agent code", ordering="agent_code")
    def code_badge(self, obj):
        return format_html(
            '<code class="gs-code">{}</code>',
            obj.agent_code,
        )

    @admin.display(description="The code agents enter")
    def agent_code_display(self, obj):
        if not obj.pk:
            return "Generated when you save."
        return format_html(
            '<code class="gs-code gs-code--large">{}</code>',
            obj.agent_code,
        )

    @admin.display(description="Name", ordering="user__full_name")
    def name(self, obj):
        return obj.user.full_name or "Unnamed"

    @admin.display(description="Email", ordering="user__email")
    def email_address(self, obj):
        return obj.user.email

    @admin.display(description="Agents")
    def team(self, obj):
        return obj.agents.count()

    @admin.display(description="Students registered")
    def verified(self, obj):
        return obj.bonuses.count()

    @admin.display(description="Bonus earned", ordering="bonus_total")
    def earned(self, obj):
        return _naira(obj.bonus_total)

    @admin.display(description="Available")
    def available(self, obj):
        return _naira(obj.available_balance)



@admin.register(SupervisorWithdrawal)
class SupervisorWithdrawalAdmin(admin.ModelAdmin):
    """Payouts a sales manager has asked for.

    The balance moved when the request was raised, so marking one paid is a
    record of the transfer and marking one failed is what gives the money back.
    """

    list_display = ("reference", "supervisor", "amount_display", "destination", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "supervisor__user__full_name",
        "supervisor__user__email",
        "supervisor__agent_code",
    )
    autocomplete_fields = ("supervisor",)
    date_hierarchy = "created_at"
    # Status moves only through the actions, never by hand (see WithdrawalAdmin).
    readonly_fields = ("reference", "supervisor", "amount", "destination", "status", "created_at", "paid_at")
    actions = ("action_mark_paid", "action_mark_failed")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("supervisor__user")

    @admin.display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return _naira(obj.amount)

    @admin.display(description="Destination")
    def destination(self, obj):
        # The account on file when the payout was requested, not today's.
        if obj.paid_to:
            return obj.paid_to
        manager = obj.supervisor
        if not manager.bank_name:
            return "No payout account on file"
        return f"{manager.bank_name} · {manager.account_number} ({manager.account_name})"

    @admin.action(description="Mark as paid out")
    def action_mark_paid(self, request, queryset):
        pending = list(
            queryset.filter(status=SupervisorWithdrawal.Status.PENDING).select_related(
                "supervisor__user"
            )
        )
        count = SupervisorWithdrawal.objects.filter(
            pk__in=[w.pk for w in pending], status=SupervisorWithdrawal.Status.PENDING
        ).update(status=SupervisorWithdrawal.Status.PAID, paid_at=timezone.now())
        paid = set(
            SupervisorWithdrawal.objects.filter(
                pk__in=[w.pk for w in pending], status=SupervisorWithdrawal.Status.PAID
            ).values_list("pk", flat=True)
        )
        for withdrawal in (w for w in pending if w.pk in paid):
            send_manager_payout_sent_email(withdrawal)
        self.message_user(request, f"{count} payout(s) marked as sent.", messages.SUCCESS)

    @admin.action(description="Mark as failed and return the balance")
    def action_mark_failed(self, request, queryset):
        count = 0
        for withdrawal in queryset.filter(status=SupervisorWithdrawal.Status.PENDING):
            if withdrawal.mark_failed():
                count += 1
                send_manager_payout_failed_email(withdrawal)
        self.message_user(
            request,
            f"{count} payout(s) failed and the balance returned.",
            messages.WARNING,
        )
