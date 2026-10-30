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
from .payout_account import (
    announce_bank_change,
    check_password_for_bank_change,
    reset_verification,
    save_profile,
    snapshot,
    verify_bank_with_paystack,
    withdrawal_hold_until,
)


class WalletSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    # Published so the portal enforces the same floor the API does, rather than
    # keeping its own copy of the number that can drift out of step. Like every
    # amount here, it is in the wallet's currency.
    minimum_withdrawal = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()
    withdrawal_hold_until = serializers.SerializerMethodField()
    symbol = serializers.CharField(read_only=True)
    loan_min = serializers.SerializerMethodField()
    loan_max = serializers.SerializerMethodField()
    ads_paid_to_meta = serializers.SerializerMethodField()

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
            "withdrawal_hold_until",
            "loan_min",
            "loan_max",
            "ads_paid_to_meta",
            "updated_at",
        )
        read_only_fields = fields

    def get_minimum_withdrawal(self, obj):
        return obj.minimum_withdrawal

    def get_can_withdraw(self, obj):
        return obj.available_balance >= obj.minimum_withdrawal

    def get_withdrawal_hold_until(self, obj):
        return withdrawal_hold_until(obj.agent)

    def get_loan_min(self, obj):
        return obj.loan_limits[0]

    def get_loan_max(self, obj):
        return obj.loan_limits[1]

    def get_ads_paid_to_meta(self, obj):
        """Whether Ads funding is paid straight to a Meta invoice (Nigeria)."""
        from .loan_payouts import meta_invoice_offered

        return meta_invoice_offered(obj.agent)


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
    # False until six hours after sign-up. The portal shows the Certificate
    # page only once this is true, and says nothing about it before.
    certificate_ready = serializers.BooleanField(read_only=True)
    # "pending" means the portal shows only the Contract page until it is signed.
    contract_status = serializers.CharField(read_only=True)
    wallet = WalletSerializer(read_only=True)
    # Paystack's bank code, when the bank was picked from Paystack's list.
    bank_code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    # True once Paystack has confirmed the account name.
    account_verified = serializers.SerializerMethodField()
    # Whether withdrawals are paid automatically through Paystack, and whether
    # they could be (switched on, agent in Nigeria) once the account is verified.
    automatic_payouts = serializers.SerializerMethodField()
    automatic_payouts_offered = serializers.SerializerMethodField()
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
            "certificate_ready",
            "contract_status",
            "address",
            "agency_name",
            "bank_name",
            "account_number",
            "account_name",
            "bank_code",
            "account_verified",
            "automatic_payouts",
            "automatic_payouts_offered",
            "current_password",
            "total_closed_sales",
            "wallet",
            "created_at",
        )
        read_only_fields = ("id", "total_closed_sales", "created_at")

    def validate_country(self, value):
        """Stored as the Exchange rates table spells it ("kenya " becomes
        "Kenya"), because the wallet's currency is looked up by this name."""
        from apps.catalog.models import OriginCountry

        name = " ".join(str(value or "").split())[:80]
        row = OriginCountry.objects.filter(name__iexact=name).only("name").first() if name else None
        return row.name if row else name

    def validate_account_number(self, value):
        if value and not (value.isdigit() and len(value) == 10):
            raise serializers.ValidationError("Account number should be 10 digits.")
        return value

    def get_account_verified(self, obj):
        return bool(obj.account_verified_at)

    def get_automatic_payouts(self, obj):
        from .payouts import can_pay_automatically

        return can_pay_automatically(obj)[0]

    def get_automatic_payouts_offered(self, obj):
        from .payouts import NIGERIA, payouts_enabled

        return payouts_enabled() and (obj.user.country or "").strip().lower() == NIGERIA

    def validate(self, attrs):
        attrs = check_password_for_bank_change(self, self.instance, attrs)
        return verify_bank_with_paystack(self, self.instance, attrs)

    def update(self, instance, validated_data):
        before = snapshot(instance)
        reset_verification(self, instance, validated_data, before)
        updated, user_data = save_profile(instance, validated_data)
        announce_bank_change(updated, before)
        if "country" in user_data:
            wallet = Wallet.objects.filter(agent=updated).first()
            if wallet is not None:
                wallet.sync_currency()
        return updated


class PayMetaInvoiceSerializer(serializers.Serializer):
    """The Meta invoice an approved Ads funding loan pays (agents in Nigeria).

    No Ads Manager link is asked for: the invoice account itself is what is
    paid. The account number must resolve through Paystack to an account in Meta's name
    (loan_payouts.is_meta_account_name). Anything else is refused and nothing
    is paid.
    """

    meta_bank_code = serializers.CharField(max_length=12)
    meta_account_number = serializers.CharField(max_length=10)

    def validate(self, attrs):
        from . import paystack_transfers as paystack
        from .loan_payouts import is_meta_account_name

        number = attrs["meta_account_number"].strip()
        code = attrs["meta_bank_code"].strip()
        if not (number.isdigit() and len(number) == 10) or not code:
            raise serializers.ValidationError(
                {"meta_account_number": "Enter the 10-digit account number and bank from your Meta invoice."}
            )
        try:
            name = paystack.resolve_account(number, code)
            bank = paystack.bank_name_for(code)
        except paystack.PaystackRejected:
            raise serializers.ValidationError(
                {"meta_account_number": "Paystack could not find this account at that bank. Check the invoice details."}
            )
        except paystack.PaystackUnreachable:
            raise serializers.ValidationError(
                {"meta_account_number": "The account could not be checked right now. Please try again in a moment."}
            )
        if not is_meta_account_name(name):
            raise serializers.ValidationError(
                {"meta_account_number": f"This account is in the name of {name}, not Meta. Use the account on your Meta ads invoice."}
            )
        return {
            "meta_bank_code": code,
            "meta_account_number": number,
            "meta_account_name": name[:120],
            "meta_bank_name": (bank or "")[:120],
        }


class LoanSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    ad_account_link = serializers.URLField(
        required=False, allow_blank=True, default="https://business.facebook.com/adsmanager"
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    # The Meta ads invoice it pays (agents in Nigeria, see loan_payouts.py).
    meta_bank_code = serializers.CharField(max_length=12, required=False, allow_blank=True)
    meta_account_number = serializers.CharField(max_length=10, required=False, allow_blank=True)
    invoice_expires_at = serializers.DateTimeField(required=False, allow_null=True)
    # Approved for a Meta invoice the agent has not paid yet: the dashboard asks for it.
    awaiting_invoice = serializers.BooleanField(read_only=True)

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
            "status_display",
            "currency",
            "requested_at",
            "disbursed_at",
            "meta_bank_code",
            "meta_bank_name",
            "meta_account_number",
            "meta_account_name",
            "invoice_expires_at",
            "failure_reason",
            "awaiting_invoice",
        )
        read_only_fields = (
            "id", "reference", "approved_amount", "status", "status_display", "currency", "requested_at",
            "disbursed_at", "meta_bank_name", "meta_account_name", "failure_reason",
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
        return self._meta_invoice(attrs)

    def _meta_invoice(self, attrs):
        """A request is only an amount and a platform.

        For an agent in Nigeria the Meta invoice is given after the desk
        approves (PayMetaInvoiceSerializer), so it can be paid the moment it is
        created and never expires while waiting for a review. Any invoice
        details sent with the request are ignored.
        """
        for field in ("meta_bank_code", "meta_account_number", "invoice_expires_at"):
            attrs.pop(field, None)
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
            "method",
            "paid_at",
            "created_at",
        )
        read_only_fields = (
            "id", "reference", "loan_deduction", "net_amount", "currency", "status", "method", "paid_at", "created_at",
        )


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
        payment = obj.fee_payment
        if payment is None:
            return "unpaid"
        return {"paid": "paid", "waived": "waived", "review": "review", "part_paid": "part_paid"}.get(
            payment.status, "pending"
        )

    def get_fee_display(self, obj):
        payment = obj.fee_payment
        if payment is None:
            return "Not paid"
        if payment.status == "waived":
            return "Waived"
        # In the student's own country's currency, as every fee screen shows it.
        from apps.payments.display import for_application, format_amount

        currency = for_application(obj)
        if payment.paid_ngn and payment.paid_ngn < payment.amount_ngn:
            return f"{format_amount(payment.paid_ngn, currency)} of {format_amount(payment.amount_ngn, currency)}"
        return format_amount(payment.amount_ngn, currency)

    def get_payment(self, obj):
        """How the fee stands, including a transfer the desk turned down."""
        from apps.payments.plans import plan_summary

        payment = obj.fee_payment
        if payment is None:
            return None
        return {
            # The 1st choice holds the fee for every school on it.
            "fee_reference": obj.fee_owner.reference,
            "plan_summary": plan_summary(payment),
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

                # Every school's file (2nd and 3rd choices too) gets them.
                targets = [application, *application.covered_applications.all()]
                for item in draft.files.all():
                    item.file.open("rb")
                    try:
                        content = item.file.read()
                    finally:
                        item.file.close()
                    for target in targets:
                        Document.objects.create(
                            application=target,
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
