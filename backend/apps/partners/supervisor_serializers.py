"""What a sales manager sees: their agents, those agents' students, the bonuses.

Everything here is read-only. A sales manager oversees rather than operates:
they do not file applications, approve anything or move money, so the portal
reports and does not act.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.applications.constants import MIN_SUPERVISOR_WITHDRAWAL_NGN
from apps.applications.models import Application

from .models import (
    AgentProfile,
    SupervisorBonus,
    SupervisorProfile,
    SupervisorWithdrawal,
)
from .serializers import AdmittedByLetterMixin
from .payout_account import announce_bank_change, check_password_for_bank_change, snapshot


class SupervisorProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    initials = serializers.CharField(source="user.initials", read_only=True)
    available_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    agent_count = serializers.SerializerMethodField()
    # Published so the portal enforces the same floor the API does, rather than
    # keeping a second copy of the number that can drift.
    minimum_withdrawal = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()
    # Needed only when the bank details change. See payout_account.py.
    current_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

    class Meta:
        model = SupervisorProfile
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "avatar",
            "initials",
            "agent_code",
            "region",
            "bank_name",
            "account_number",
            "account_name",
            "current_password",
            "bonus_total",
            "total_withdrawn",
            "available_balance",
            "agent_count",
            "minimum_withdrawal",
            "can_withdraw",
            "is_active",
            "created_at",
        )
        read_only_fields = (
            "id",
            "agent_code",
            "bonus_total",
            "total_withdrawn",
            "available_balance",
            "agent_count",
            "minimum_withdrawal",
            "can_withdraw",
            "is_active",
            "created_at",
        )

    def get_agent_count(self, obj):
        return obj.agents.count()

    def get_minimum_withdrawal(self, obj):
        return MIN_SUPERVISOR_WITHDRAWAL_NGN

    def get_can_withdraw(self, obj):
        """Enough banked, and somewhere to send it."""
        return (
            obj.available_balance >= MIN_SUPERVISOR_WITHDRAWAL_NGN
            and bool(obj.bank_name)
            and bool(obj.account_number)
        )

    def validate(self, attrs):
        return check_password_for_bank_change(self, self.instance, attrs)

    def update(self, instance, validated_data):
        before = snapshot(instance)
        user_data = validated_data.pop("user", {})
        for field, value in user_data.items():
            setattr(instance.user, field, value)
        if user_data:
            instance.user.save()
        updated = super().update(instance, validated_data)
        announce_bank_change(updated, before)
        return updated


class SupervisedAgentSerializer(serializers.ModelSerializer):
    """One agent, summarised by what they have actually produced."""

    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    initials = serializers.CharField(source="user.initials", read_only=True)
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    partner_code = serializers.CharField(read_only=True)
    joined_at = serializers.DateTimeField(source="created_at", read_only=True)

    students = serializers.SerializerMethodField()
    fees_paid = serializers.SerializerMethodField()
    admitted = serializers.SerializerMethodField()
    visas_verified = serializers.SerializerMethodField()
    earned = serializers.SerializerMethodField()
    bonus_from_agent = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = AgentProfile
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "initials",
            "avatar",
            "partner_code",
            "agency_name",
            "joined_at",
            "students",
            "fees_paid",
            "admitted",
            "visas_verified",
            "earned",
            "bonus_from_agent",
            "last_activity",
        )

    # The queryset annotates these, so a table of agents is one query rather
    # than one per row.
    def get_students(self, obj):
        return getattr(obj, "student_count", obj.applications.count())

    def get_fees_paid(self, obj):
        return getattr(obj, "paid_count", 0)

    def get_admitted(self, obj):
        return getattr(obj, "admitted_count", 0)

    def get_visas_verified(self, obj):
        return getattr(obj, "visa_count", 0)

    def get_earned(self, obj):
        """What the agent has earned, in Naira, so every agent reads alike."""
        from django.db.models import Sum

        return obj.commissions.aggregate(total=Sum("amount_ngn"))["total"] or Decimal("0.00")

    def get_bonus_from_agent(self, obj):
        return sum(
            (bonus.amount for bonus in obj.supervisor_bonuses.all()), Decimal("0.00")
        )

    def get_last_activity(self, obj):
        return getattr(obj, "last_submission", None)


class SupervisedStudentSerializer(AdmittedByLetterMixin, serializers.ModelSerializer):
    """A student filed by one of this sales manager's agents."""

    agent = serializers.CharField(source="submitted_by_agent.user.full_name", read_only=True)
    agent_id = serializers.IntegerField(source="submitted_by_agent.id", read_only=True)
    institution = serializers.CharField(source="institution.name", default="", read_only=True)
    destination_country = serializers.CharField(
        source="destination_country.name", read_only=True
    )
    origin_country = serializers.CharField(source="origin_country.name", read_only=True)
    program = serializers.SerializerMethodField()
    fee_status = serializers.SerializerMethodField()
    fee_display = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "reference",
            "full_name",
            "email",
            "agent",
            "agent_id",
            "origin_country",
            "destination_country",
            "institution",
            "program",
            "status",
            "visa_status",
            "fee_status",
            "fee_display",
            "submitted_at",
        )

    def get_program(self, obj):
        return " and ".join(p.name for p in obj.programs.all())

    def get_fee_status(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "unpaid"
        return {"paid": "paid", "waived": "waived"}.get(payment.status, "pending")

    def get_fee_display(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "Not paid"
        if payment.status == "waived":
            return "Waived"
        return payment.display_total


class SupervisorBonusSerializer(serializers.ModelSerializer):
    agent = serializers.CharField(source="agent.user.full_name", default="", read_only=True)
    student = serializers.CharField(source="application.full_name", read_only=True)
    reference = serializers.CharField(source="application.reference", read_only=True)
    institution = serializers.CharField(
        source="application.institution.name", default="", read_only=True
    )

    class Meta:
        model = SupervisorBonus
        fields = ("id", "amount", "earned_at", "agent", "student", "reference", "institution")


class SupervisorWithdrawalSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = SupervisorWithdrawal
        fields = ("id", "reference", "amount", "status", "created_at", "paid_at")
        read_only_fields = fields


class SupervisorWithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, value):
        supervisor = self.context["supervisor"]

        if value < MIN_SUPERVISOR_WITHDRAWAL_NGN:
            raise serializers.ValidationError(
                f"The smallest withdrawal is ₦{MIN_SUPERVISOR_WITHDRAWAL_NGN:,.0f}."
            )
        if value > supervisor.available_balance:
            raise serializers.ValidationError("That is more than your available balance.")
        if not supervisor.bank_name or not supervisor.account_number:
            raise serializers.ValidationError(
                "Add your payout account on your profile before requesting a withdrawal."
            )
        return value
