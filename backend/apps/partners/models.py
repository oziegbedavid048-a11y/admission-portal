"""Partner agents: the people who recruit students and earn commission.

An agent registers students, is paid a fixed commission at two milestones
(admission granted, visa verified), can borrow interest-free capital to run
recruitment ads, and withdraws the balance to a registered bank account.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.applications.uploads import draft_upload_path
from apps.applications.constants import (
    AGENT_COMMISSION_PER_MILESTONE,
    LOAN_REPAYMENT_RATE,
    MIN_SUPERVISOR_WITHDRAWAL_NGN,
    MIN_WITHDRAWAL_NGN,
    SUPERVISOR_BONUS_NGN,
)


class AgentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_profile",
    )
    agency_name = models.CharField(max_length=160, blank=True)
    bank_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=10)
    account_name = models.CharField(max_length=120)
    total_closed_sales = models.PositiveIntegerField(default=0)
    supervisor = models.ForeignKey(
        "partners.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents",
        help_text="The sales manager whose code this agent used at sign-up.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "agent"
        verbose_name_plural = "agents"

    def __str__(self):
        return f"{self.user.full_name or self.user.email} (agent)"

    @property
    def partner_code(self):
        """A stable, quotable identifier the agent can give to a student."""
        return f"AGT-{self.pk:05d}"


# Ambiguous characters are left out so a code can be read aloud down a phone
# line without anyone mistaking O for 0 or I for 1.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_agent_code():
    """The code a sales manager hands to the agents who report to them."""
    return "GSA-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


class SupervisorProfile(models.Model):
    """A sales manager: someone who recruits and oversees a group of agents.

    A sales manager does not file applications. They are given an agent code
    when the admissions desk creates their account, agents enter that code when
    they sign up, and from then on the sales manager can see those agents and
    the students they register. They earn a bonus each time one of those agents
    registers a student.

    The class keeps its original name so the database table and every migration
    stay put; only what people read has changed.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="supervisor_profile",
    )
    agent_code = models.CharField(
        max_length=12,
        unique=True,
        default=generate_agent_code,
        help_text="Agents enter this when they register to join this sales manager.",
    )
    region = models.CharField(
        max_length=120, blank=True, help_text="Territory or team this sales manager covers."
    )
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    account_name = models.CharField(max_length=120, blank=True)

    bonus_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_withdrawn = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Turning this off stops the code being accepted by new agents.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sales manager"
        verbose_name_plural = "sales managers"

    def __str__(self):
        return f"{self.user.full_name or self.user.email} ({self.agent_code})"

    @property
    def available_balance(self):
        return max(Decimal("0.00"), self.bonus_total - self.total_withdrawn)

    def credit_bonus(self, amount=SUPERVISOR_BONUS_NGN):
        self.bonus_total += amount
        self.save(update_fields=["bonus_total"])


class SupervisorBonus(models.Model):
    """One sales-manager bonus, tied to the registration that earned it.

    Unique per application, so a retried registration never pays twice.
    """

    supervisor = models.ForeignKey(
        SupervisorProfile, on_delete=models.CASCADE, related_name="bonuses"
    )
    agent = models.ForeignKey(
        AgentProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="supervisor_bonuses",
        help_text="The agent who registered the student.",
    )
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="supervisor_bonuses"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=SUPERVISOR_BONUS_NGN
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-earned_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("application",), name="one_supervisor_bonus_per_application"
            )
        ]
        verbose_name = "sales manager bonus"
        verbose_name_plural = "sales manager bonuses"

    def __str__(self):
        return f"Bonus {self.amount} · {self.application.reference}"


class Wallet(models.Model):
    """Running totals for one agent.

    ``available_balance`` is derived, never set by hand: it is everything earned
    minus what is owed on a loan, already withdrawn, or moved into savings.
    """

    agent = models.OneToOneField(
        AgentProfile, on_delete=models.CASCADE, related_name="wallet"
    )
    registration_commission_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    visa_commission_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_earned = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    loan_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    saved_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_withdrawn = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.agent}"

    @property
    def available_balance(self):
        balance = (
            self.total_earned
            - self.loan_balance
            - self.total_withdrawn
            - self.saved_balance
        )
        return max(Decimal("0.00"), balance)

    @transaction.atomic
    def move_to_savings(self, amount):
        """Set money aside. It stops being withdrawable until it is released."""
        wallet = Wallet.objects.select_for_update().get(pk=self.pk)
        if amount <= 0:
            raise ValidationError("Enter an amount to save.")
        if amount > wallet.available_balance:
            raise ValidationError("That is more than your available balance.")
        wallet.saved_balance += amount
        wallet.save(update_fields=["saved_balance"])
        return wallet

    @transaction.atomic
    def release_from_savings(self, amount):
        """Take money back out of savings.

        Savings used to be one-way: the only endpoint moved money in, and
        `available_balance` subtracts what is saved, so anything put aside stopped
        being withdrawable permanently. Money the agent has earned has to be
        reachable again, so this is the way back.
        """
        wallet = Wallet.objects.select_for_update().get(pk=self.pk)
        if amount <= 0:
            raise ValidationError("Enter an amount to release.")
        if amount > wallet.saved_balance:
            raise ValidationError("That is more than you have in savings.")
        wallet.saved_balance -= amount
        wallet.save(update_fields=["saved_balance"])
        return wallet

    def credit_commission(self, kind, amount):
        if kind == Commission.Kind.REGISTRATION:
            self.registration_commission_total += amount
        else:
            self.visa_commission_total += amount
        self.total_earned += amount
        self.save()


class Commission(models.Model):
    """One commission payment, tied to the student file that earned it.

    An agent earns twice per student: once the moment the application fee is
    paid, and again once the admissions desk confirms the visa. Nothing is
    credited on an unpaid file, so the balance only ever reflects money the
    business has actually received.
    """

    class Kind(models.TextChoices):
        REGISTRATION = "registration", "Student registered and fee paid"
        VISA = "visa", "Visa verified"

    agent = models.ForeignKey(
        AgentProfile, on_delete=models.CASCADE, related_name="commissions"
    )
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="commissions"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=AGENT_COMMISSION_PER_MILESTONE
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-earned_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("application", "kind"), name="one_commission_per_milestone"
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.application.reference}"


class Loan(models.Model):
    """Interest-free ads funding, repaid out of later withdrawals."""

    class Status(models.TextChoices):
        PENDING = "pending", "In review"
        APPROVED = "approved", "Approved"
        DISBURSED = "disbursed", "Disbursed"
        REPAID = "repaid", "Repaid"
        DECLINED = "declined", "Declined"

    MIN_AMOUNT = Decimal("10000")
    MAX_AMOUNT = Decimal("80000")

    agent = models.ForeignKey(
        AgentProfile, on_delete=models.CASCADE, related_name="loans"
    )
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    purpose = models.CharField(max_length=80, help_text="Advertising platform.")
    ad_account_link = models.URLField(max_length=400, blank=True, default="")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at",)
        indexes = [
            models.Index(fields=["status"], name="loan_status_idx"),
        ]
        verbose_name = "ads funding request"
        verbose_name_plural = "ads funding requests"

    def __str__(self):
        return f"Loan {self.reference} · {self.get_status_display()}"

    @property
    def reference(self):
        return f"LN-{self.pk:05d}"


class Withdrawal(models.Model):
    """A payout request.

    While a loan is outstanding, a tenth of each withdrawal is held back and
    applied to it, so the agent repays as they earn rather than in one lump.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "In review"
        PAID = "completed", "Paid out"
        FAILED = "rejected", "Failed"

    MIN_AMOUNT = MIN_WITHDRAWAL_NGN

    agent = models.ForeignKey(
        AgentProfile, on_delete=models.CASCADE, related_name="withdrawals"
    )
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    loan_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"], name="withdrawal_status_idx"),
        ]
        verbose_name = "agent payout"
        verbose_name_plural = "agent payouts"

    def __str__(self):
        return f"{self.reference} · {self.amount_requested}"

    @property
    def reference(self):
        return f"WD-{self.pk:05d}"

    @classmethod
    @transaction.atomic
    def request(cls, agent, amount):
        """Create a withdrawal and move the wallet on in one step.

        The wallet row is locked for the length of this transaction and the
        balance is re-read inside it. The serializer checks the balance too, but
        that check and this write are two separate moments: two requests sent at
        the same time both passed validation against the same balance and both
        got paid. Locking the row makes the second one wait, see the balance the
        first one left behind, and be refused.
        """
        wallet = Wallet.objects.select_for_update().get(agent=agent)

        if amount < cls.MIN_AMOUNT:
            raise ValidationError(
                f"The smallest withdrawal is ₦{cls.MIN_AMOUNT:,.0f}."
            )
        if amount > wallet.available_balance:
            raise ValidationError("That is more than your available balance.")

        deduction = Decimal("0.00")
        if wallet.loan_balance > 0:
            deduction = min(
                (amount * LOAN_REPAYMENT_RATE).quantize(Decimal("0.01")),
                wallet.loan_balance,
            )

        withdrawal = cls.objects.create(
            agent=agent,
            amount_requested=amount,
            loan_deduction=deduction,
            net_amount=amount - deduction,
        )

        wallet.loan_balance = max(Decimal("0.00"), wallet.loan_balance - deduction)
        wallet.total_withdrawn += amount
        wallet.save()

        if wallet.loan_balance == 0:
            agent.loans.filter(status=Loan.Status.DISBURSED).update(
                status=Loan.Status.REPAID
            )
        return withdrawal


class SupervisorWithdrawal(models.Model):
    """A sales manager asking for their bonus balance to be paid out.

    Simpler than the agent equivalent: there is no ad-funding loan to repay, so
    the amount requested is the amount sent. Raising one moves the balance
    straight away, which is what stops the same money being requested twice
    while the first payout is still being processed.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "In review"
        PAID = "completed", "Paid out"
        FAILED = "rejected", "Failed"

    MIN_AMOUNT = MIN_SUPERVISOR_WITHDRAWAL_NGN

    supervisor = models.ForeignKey(
        SupervisorProfile, on_delete=models.CASCADE, related_name="withdrawals"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "sales manager payout"
        verbose_name_plural = "sales manager payouts"

    def __str__(self):
        return f"{self.reference} · {self.amount}"

    @property
    def reference(self):
        return f"SMW-{self.pk:05d}"

    @classmethod
    @transaction.atomic
    def request(cls, supervisor, amount):
        """Same lock as the agent payout, for the same reason."""
        from apps.applications.constants import MIN_SUPERVISOR_WITHDRAWAL_NGN

        locked = SupervisorProfile.objects.select_for_update().get(pk=supervisor.pk)

        if amount < MIN_SUPERVISOR_WITHDRAWAL_NGN:
            raise ValidationError(
                f"The smallest withdrawal is ₦{MIN_SUPERVISOR_WITHDRAWAL_NGN:,.0f}."
            )
        if amount > locked.available_balance:
            raise ValidationError("That is more than your available balance.")

        withdrawal = cls.objects.create(supervisor=locked, amount=amount)
        locked.total_withdrawn += amount
        locked.save(update_fields=["total_withdrawn"])
        supervisor.total_withdrawn = locked.total_withdrawn
        return withdrawal

    @transaction.atomic
    def mark_failed(self):
        """Give the money back. A payout that never left has to be returned."""
        if self.status == self.Status.FAILED:
            return False
        self.status = self.Status.FAILED
        self.save(update_fields=["status"])

        supervisor = self.supervisor
        supervisor.total_withdrawn = max(
            Decimal("0.00"), supervisor.total_withdrawn - self.amount
        )
        supervisor.save(update_fields=["total_withdrawn"])
        return True



class StudentDraft(models.Model):
    """A student registration an agent started and will finish later.

    Holds what was typed as JSON, exactly as the registration form keeps it,
    so a draft reopens on the step it was left on.
    """

    agent = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, related_name="drafts")
    step = models.PositiveSmallIntegerField(default=1)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "student draft"
        verbose_name_plural = "student drafts"

    def __str__(self):
        return f"Draft: {self.data.get('fullName') or 'unnamed student'}"

    @property
    def student_name(self):
        return (self.data or {}).get("fullName", "")


class StudentDraftFile(models.Model):
    """A document attached to a draft. Becomes a real document on submit."""

    draft = models.ForeignKey(StudentDraft, on_delete=models.CASCADE, related_name="files")
    # passport, academic, cv, or other-<n> for extra documents.
    slot = models.CharField(max_length=24)
    kind = models.CharField(max_length=16, default="other")
    name = models.CharField(max_length=160)
    file = models.FileField(upload_to=draft_upload_path)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)
        constraints = [
            models.UniqueConstraint(fields=["draft", "slot"], name="one_file_per_draft_slot"),
        ]
