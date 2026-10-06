from decimal import Decimal

from django.db import transaction

from rest_framework import serializers

from apps.accounts.models import User
from apps.applications.constants import AGENT_COMMISSION_PER_MILESTONE
from apps.applications import services
from apps.applications.models import Application, Notification
from apps.applications.serializers import ApplicationCreateSerializer

from .models import (
    AgentProfile,
    Commission,
    Loan,
    StudentDraft,
    StudentDraftFile,
    Wallet,
    Withdrawal,
    loan_block_reason,
)
from .payout_account import announce_bank_change, check_password_for_bank_change, snapshot


class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    # Published so the portal enforces the same floor the API does, rather than
    # keeping its own copy of the number that can drift out of step. Like every
    # amount here, it is in the wallet's currency.
    minimum_withdrawal = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()
    symbol = serializers.CharField(read_only=True)
    loan_min = serializers.SerializerMethodField()
    loan_max = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            "registration_commission_total",
            "visa_commission_total",
            "total_earned",
            "loan_balance",
            "saved_balance",
            "total_withdrawn",
            "loan_repaid_total",
            "available_balance",
            "currency",
            "symbol",
            "minimum_withdrawal",
            "can_withdraw",
            "loan_min",
            "loan_max",
            "updated_at",
        )
        read_only_fields = fields

    def get_minimum_withdrawal(self, obj):
        return obj.minimum_withdrawal

    def get_can_withdraw(self, obj):
        return obj.available_balance >= obj.minimum_withdrawal

    def get_loan_min(self, obj):
        return obj.loan_limits[0]

    def get_loan_max(self, obj):
        return obj.loan_limits[1]


class AgentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    country = serializers.CharField(
        source="user.country", required=False, allow_blank=True
    )
    avatar = serializers.ImageField(source="user.avatar", read_only=True)
    initials = serializers.CharField(source="user.initials", read_only=True)
    partner_code = serializers.CharField(read_only=True)
    wallet = WalletSerializer(read_only=True)
    # Needed only when the bank details change. See payout_account.py.
    current_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

    class Meta:
        model = AgentProfile
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "country",
            "avatar",
            "initials",
            "partner_code",
            "agency_name",
            "bank_name",
            "account_number",
            "account_name",
            "current_password",
            "total_closed_sales",
            "wallet",
            "created_at",
        )
        read_only_fields = ("id", "total_closed_sales", "created_at")

    def validate_account_number(self, value):
        if value and not (value.isdigit() and len(value) == 10):
            raise serializers.ValidationError("Account number should be 10 digits.")
        return value

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
        if "country" in user_data:
            wallet = Wallet.objects.filter(agent=updated).first()
            if wallet is not None:
                wallet.sync_currency()
        return updated


class LoanSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    ad_account_link = serializers.URLField(
        required=False, allow_blank=True, default="https://business.facebook.com/adsmanager"
    )

    class Meta:
        model = Loan
        fields = (
            "id",
            "reference",
            "requested_amount",
            "approved_amount",
            "purpose",
            "ad_account_link",
            "status",
            "currency",
            "requested_at",
            "disbursed_at",
        )
        read_only_fields = (
            "id", "reference", "approved_amount", "status", "currency", "requested_at", "disbursed_at",
        )

    def validate_requested_amount(self, value):
        """The range is set in Naira and applied in the agent's currency."""
        agent = self.context.get("agent")
        if agent is None:
            low, high = Loan.MIN_AMOUNT, Loan.MAX_AMOUNT
            wallet = None
        else:
            wallet, _ = Wallet.objects.get_or_create(agent=agent)
            wallet.sync_currency()
            low, high = wallet.loan_limits
        if value < low or value > high:
            show = wallet.money if wallet else (lambda amount: f"₦{amount:,.0f}")
            raise serializers.ValidationError(f"Ads funding runs from {show(low)} to {show(high)}.")
        return value

    def validate(self, attrs):
        """One loan at a time, and nothing new until the last is repaid.

        The per-request ceiling was the only limit, so an agent could file ten
        requests of the maximum and, if each were approved, hold ten times the
        cap. The view checks this again under a lock when it saves.
        """
        reason = loan_block_reason(self.context["agent"])
        if reason:
            raise serializers.ValidationError(reason)
        return attrs

    def validate_purpose(self, value):
        if not value.strip():
            raise serializers.ValidationError("Choose an advertising platform.")
        return value


class RepayLoanSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1"))


class WithdrawalSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = Withdrawal
        fields = (
            "id",
            "reference",
            "amount_requested",
            "loan_deduction",
            "net_amount",
            "currency",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "reference", "loan_deduction", "net_amount", "currency", "status", "created_at")


class WithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, value):
        """A friendly check before the request is made.

        The authoritative one is in Withdrawal.request, under a row lock. This
        exists so the common case gets a clear message on the field rather than
        an error from the model.
        """
        agent = self.context["agent"]
        wallet = agent.wallet
        minimum = wallet.minimum_withdrawal
        if value < minimum:
            raise serializers.ValidationError(
                f"The smallest withdrawal is {wallet.money(minimum)}."
            )
        if value > wallet.available_balance:
            raise serializers.ValidationError("That is more than your available balance.")
        return value


class SaveToSavingsSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1"))

    def validate_amount(self, value):
        agent = self.context["agent"]
        if value > agent.wallet.available_balance:
            raise serializers.ValidationError("That is more than your available balance.")
        return value


class ReleaseFromSavingsSerializer(serializers.Serializer):
    """Take money back out of savings and make it withdrawable again."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1"))

    def validate_amount(self, value):
        agent = self.context["agent"]
        if value > agent.wallet.saved_balance:
            raise serializers.ValidationError("That is more than you have in savings.")
        return value


class CommissionSerializer(serializers.ModelSerializer):
    application_reference = serializers.CharField(
        source="application.reference", read_only=True
    )
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    student_name = serializers.CharField(source="application.full_name", read_only=True)

    class Meta:
        model = Commission
        fields = (
            "id",
            "kind",
            "kind_display",
            "amount",
            "currency",
            "earned_at",
            "application_reference",
            "student_name",
        )


class AdmittedByLetterMixin:
    """A student whose admission or offer letter has been published reads as
    Admitted in the tables, matching the Admitted count on the overview. Only
    a file still waiting (submitted or in review) is changed: the stored status
    is not touched, and a rejected file stays rejected."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("status") in (Application.Status.SUBMITTED, Application.Status.IN_REVIEW):
            if services.reads_as_admitted(instance):
                data["status"] = Application.Status.ADMITTED
        return data


class AgentStudentSerializer(AdmittedByLetterMixin, serializers.ModelSerializer):
    """A student file as the agent's Students table shows it."""

    institution = serializers.CharField(source="institution.name", default="", read_only=True)
    destination_country = serializers.CharField(
        source="destination_country.name", read_only=True
    )
    origin_country = serializers.CharField(source="origin_country.name", read_only=True)
    program = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    commission_earned = serializers.SerializerMethodField()
    fee_status = serializers.SerializerMethodField()
    fee_display = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    verification = serializers.SerializerMethodField()
    letters = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "reference",
            "full_name",
            "email",
            "phone",
            "origin_country",
            "destination_country",
            "institution",
            "program",
            "qualification",
            "year_graduated",
            "grade_gpa",
            "status",
            "visa_status",
            "notes",
            "documents",
            "commission_earned",
            "fee_status",
            "fee_display",
            "payment",
            "verification",
            "letters",
            "submitted_at",
        )
        # Everything here is read-only. This serializer is what the agent's
        # Students table renders, and it used to be writable: a PATCH could set
        # `status`, `visa_status` or the student's own `email`, which is where
        # every letter and status update is sent. The desk decides what a file's
        # status is, and the only field an agent may still change is the note
        # they wrote themselves, which AgentStudentNoteSerializer handles.
        read_only_fields = fields

    def get_program(self, obj):
        return " & ".join(p.name for p in obj.programs.all())

    def get_documents(self, obj):
        return [
            {"id": doc.id, "name": doc.name, "status": doc.status, "review_note": doc.review_note}
            for doc in obj.documents.all()
        ]

    def get_commission_earned(self, obj):
        return sum((c.amount for c in obj.commissions.all()), Decimal("0.00"))

    def get_fee_status(self, obj):
        """Whether the application fee has been settled.

        This is what gates the agent's commission, so the students table shows
        it on every row rather than making them open each file to find out.
        """
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "unpaid"
        return {"paid": "paid", "waived": "waived", "review": "review"}.get(payment.status, "pending")

    def get_fee_display(self, obj):
        payment = getattr(obj, "payment", None)
        if payment is None:
            return "Not paid"
        if payment.status == "waived":
            return "Waived"
        return payment.display_total

    def get_payment(self, obj):
        """How the fee stands, including a transfer the desk turned down."""
        payment = getattr(obj, "payment", None)
        if payment is None:
            return None
        return {
            "status": payment.status,
            "status_label": payment.get_status_display(),
            "method": payment.gateway,
            "display_total": payment.display_total,
            "review_note": payment.review_note,
            "transfer_bank": payment.transfer_bank,
            "paid_at": payment.paid_at,
        }

    def get_verification(self, obj):
        """The same checks the admissions desk ticks in the admin."""
        summary = obj.verification_summary
        return {
            "status": summary["status"],
            "status_label": obj.get_verification_status_display(),
            "checkpoints": [
                {"key": c["key"], "label": c["label"], "verified": c["verified"]}
                for c in summary["checkpoints"]
            ],
        }

    def get_letters(self, obj):
        letters = []
        for letter in obj.letters.all():
            if not letter.is_published or not letter.file:
                continue
            url = letter.file.url
            letters.append(
                {
                    "id": letter.id,
                    "title": letter.title,
                    "kind": letter.get_kind_display(),
                    "url": url,
                    "issued_at": letter.issued_at,
                }
            )
        return letters


class AgentStudentNoteSerializer(serializers.ModelSerializer):
    """The agent's own note on a file they filed, and nothing else."""

    class Meta:
        model = Application
        fields = ("notes",)


class AgentStudentCreateSerializer(ApplicationCreateSerializer):
    """The agent version of the wizard: it also provisions the student account.

    The student gets their own login so they can follow the file in the
    applicant portal, with a one-time password returned to the agent to hand
    over.
    """

    # A saved draft whose documents should join this application.
    draft = serializers.IntegerField(required=False, write_only=True)

    def validate_email(self, value):
        """An agent may only file under an email that is new, or that belongs
        to a student this agent registered before.

        Anyone can open an agent account, and the email used to be matched to
        any existing account with no other check, so an agent could plant a
        file, with their notes and fee prompts, in a real applicant's
        dashboard, or attach a file to a staff or agent account.
        """
        email = value.strip().lower()
        existing = User.objects.filter(email__iexact=email).first()
        if existing is None:
            return email
        agent = getattr(self.context["request"].user, "agent_profile", None)
        registered_by_this_agent = (
            existing.role == User.Role.APPLICANT
            and not existing.has_usable_password()
            and existing.applications.exists()
            and not existing.applications.exclude(submitted_by_agent=agent).exists()
        )
        if not registered_by_this_agent:
            raise serializers.ValidationError(
                "This email already belongs to a Gabstep account. Use the student's "
                "own email address, or ask them to apply from their account."
            )
        return email

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        agent = request.user.agent_profile
        draft_id = validated_data.pop("draft", None)

        email = validated_data["email"].lower()
        student = User.objects.filter(email__iexact=email).first()
        account_created = False
        if student is None:
            # The account exists to hold the file, not to be signed into. Nobody
            # is given a password for it: the student is never written to, and
            # the agent handles the file on their behalf. An unusable password
            # means no secret is created that would then have to be delivered
            # somewhere. Staff can set one from the admin if access is ever
            # genuinely needed.
            student = User.objects.create_user(
                email=email,
                password=None,
                full_name=validated_data["full_name"],
                phone=validated_data["phone"],
                role=User.Role.APPLICANT,
            )
            account_created = True

        validated_data["applicant"] = student
        validated_data["agent"] = agent
        application = super().create(validated_data)

        agent_name = request.user.full_name or request.user.email
        application.notes = (
            application.notes
            or f"Registered through the partner portal by {agent_name}."
        )
        application.save(update_fields=["notes"])
        Notification.objects.create(
            application=application,
            text=f"Filed by your education partner, {agent_name}.",
            send_email=False,
        )

        # The sales manager's bonus is not paid here. It waits for the
        # student's application fee to be paid (payments/settlement.py).

        # A draft's documents become the application's documents, and the
        # draft is finished with.
        if draft_id:
            draft = StudentDraft.objects.filter(pk=draft_id, agent=agent).first()
            if draft is not None:
                from django.core.files.base import ContentFile

                from apps.applications.models import Document

                for item in draft.files.all():
                    item.file.open("rb")
                    try:
                        content = item.file.read()
                    finally:
                        item.file.close()
                    Document.objects.create(
                        application=application,
                        kind=item.kind,
                        name=item.name,
                        original_filename=item.original_filename,
                        file=ContentFile(content, name=item.original_filename or "document"),
                    )
                draft.delete()

        from apps.accounts.emails import send_agent_student_registered_email

        transaction.on_commit(lambda: send_agent_student_registered_email(application))

        application.account_created = account_created
        return application



class StudentDraftFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDraftFile
        fields = ("id", "slot", "kind", "name", "original_filename", "uploaded_at")
        read_only_fields = fields


class StudentDraftSerializer(serializers.ModelSerializer):
    """A half-finished registration: the form as typed, and its documents."""

    files = StudentDraftFileSerializer(many=True, read_only=True)
    student_name = serializers.CharField(read_only=True)

    class Meta:
        model = StudentDraft
        fields = ("id", "step", "data", "student_name", "files", "created_at", "updated_at")
        read_only_fields = ("id", "student_name", "files", "created_at", "updated_at")

    def validate_step(self, value):
        return min(max(int(value or 1), 1), 5)

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Draft data must be an object.")
        return value
