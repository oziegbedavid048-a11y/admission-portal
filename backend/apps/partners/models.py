"""Partner agents: the people who recruit students and earn commission.

An agent registers students, is paid a fixed commission at two milestones
(admission granted, visa verified), can borrow interest-free capital to run
recruitment ads, and withdraws the balance to a registered bank account.
"""

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F

from apps.applications.uploads import draft_upload_path
from apps.applications.constants import (
    AGENT_COMMISSION_PER_MILESTONE,
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
    # Set when the bank is picked from Paystack's list and Paystack confirms the
    # account name. Only a verified account is paid automatically.
    bank_code = models.CharField(max_length=12, blank=True)
    account_verified_at = models.DateTimeField(null=True, blank=True)
    # Paystack's handle for this account, made on the first automatic payout
    # and cleared whenever the bank details change.
    paystack_recipient_code = models.CharField(max_length=40, blank=True)
    # When payouts were last pointed at a different account. Withdrawals pause
    # for a while afterwards (see payout_account.withdrawal_hold_until).
    payout_account_changed_at = models.DateTimeField(null=True, blank=True)
    total_closed_sales = models.PositiveIntegerField(default=0)
    supervisor = models.ForeignKey(
        "partners.SupervisorProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents",
        help_text="The sales manager whose code this agent used at sign-up.",
    )
    # Given at sign-up, and printed on the partnership contract.
    address = models.CharField(max_length=255, blank=True)
    # Whether this agent must sign the partnership contract in the portal before
    # using it. Set by agent sign-up, so everyone who registers from now on is
    # asked; agents who joined before the contract page existed are not (staff
    # upload their paper contract instead, see AgentContract).
    contract_required = models.BooleanField(
        default=False,
        help_text="Must sign the partnership contract in the portal before using it.",
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

    # The partnership certificate is not handed over the moment an agent signs
    # up. It appears in the portal this long after the account was set up, and
    # nothing in the portal mentions it before then.
    CERTIFICATE_DELAY = timedelta(hours=6)

    @property
    def certificate_ready_at(self):
        """When the partnership certificate appears, and the date printed on it."""
        return self.created_at + self.CERTIFICATE_DELAY

    @property
    def contract_status(self):
        """"signed", "pending" (must sign before using the portal) or "none"."""
        contract = getattr(self, "contract", None)
        if contract is not None and contract.file:
            return "signed"
        return "pending" if self.contract_required else "none"

    @property
    def certificate_ready(self):
        from django.utils import timezone

        return bool(self.created_at) and timezone.now() >= self.certificate_ready_at


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
    # As on AgentProfile: set when Paystack confirms the account, and used to
    # pay withdrawals automatically.
    bank_code = models.CharField(max_length=12, blank=True)
    account_verified_at = models.DateTimeField(null=True, blank=True)
    paystack_recipient_code = models.CharField(max_length=40, blank=True)
    payout_account_changed_at = models.DateTimeField(null=True, blank=True)

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
        # Added in the database, not on this copy: a copy read before a payout
        # request would otherwise write its stale totals back over it.
        SupervisorProfile.objects.filter(pk=self.pk).update(bonus_total=F("bonus_total") + amount)
        self.refresh_from_db(fields=["bonus_total"])


class SupervisorBonus(models.Model):
    """One sales-manager bonus, tied to the paid application that earned it.

    Unique per application, so a retried settlement never pays twice.
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
        indexes = [
            models.Index(fields=["supervisor", "-earned_at"], name="bonus_manager_earned_idx"),
        ]
        verbose_name = "sales manager bonus"
        verbose_name_plural = "sales manager bonuses"

    def __str__(self):
        return f"Bonus {self.amount} · {self.application.reference}"


class Wallet(models.Model):
    """Running totals for one agent.

    ``available_balance`` is derived, never set by hand: it is everything earned
    minus what is already withdrawn or moved into savings.

    An Ads funding loan is not taken out of it, and nothing is taken out of a
    withdrawal for it either. Approving a loan used to subtract the whole loan
    from this balance, which wiped out the agent's earnings on the spot.

    ``loan_balance`` is what is still owed. The agent repays it from this
    balance with ``repay_loan`` (the Repay button), which moves the amount into
    ``loan_repaid_total``; the desk can also clear a loan repaid some other way
    with "Mark as repaid" in the admin. A new loan cannot be requested while
    any is owed (see loan_block_reason).
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
    # Earnings the agent has used to pay back Ads funding.
    loan_repaid_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    # Every amount above is in this currency: Naira for an agent in Nigeria,
    # the agent's own country's currency anywhere else (see currency.py). It
    # follows the agent's country until the first money lands, then stays.
    currency = models.CharField(max_length=8, default="NGN")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.agent}"

    @property
    def is_empty(self):
        """No money has ever moved through this wallet."""
        return not any(
            (
                self.total_earned,
                self.loan_balance,
                self.saved_balance,
                self.total_withdrawn,
                self.loan_repaid_total,
            )
        )

    def sync_currency(self):
        """Match the agent's country, while nothing is in the wallet yet.

        Once money has landed the currency is fixed, so a balance is never
        relabelled in a currency it was not earned in. Returns True if changed.
        """
        from .currency import currency_for_country

        if not self.is_empty:
            return False
        currency, _ = currency_for_country(self.agent.user.country)
        if currency == self.currency:
            return False
        self.currency = currency
        if self.pk:
            Wallet.objects.filter(pk=self.pk).update(currency=currency)
        return True

    @property
    def symbol(self):
        from .currency import symbol_for

        return symbol_for(self.currency)

    def money(self, amount):
        from .currency import money

        return money(amount, self.currency, self.symbol)

    @property
    def minimum_withdrawal(self):
        """The smallest payout, set in Naira, in this wallet's currency today."""
        from .currency import threshold_from_naira

        return threshold_from_naira(MIN_WITHDRAWAL_NGN, self.currency)

    @property
    def loan_limits(self):
        """Smallest and largest Ads funding request, in this wallet's currency."""
        from .currency import threshold_from_naira

        return (
            threshold_from_naira(Loan.MIN_AMOUNT, self.currency),
            threshold_from_naira(Loan.MAX_AMOUNT, self.currency),
        )

    @property
    def available_balance(self):
        balance = (
            self.total_earned
            - self.total_withdrawn
            - self.saved_balance
            - self.loan_repaid_total
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

    @transaction.atomic
    def repay_loan(self, amount):
        """Pay back Ads funding out of the available balance.

        The wallet row is locked and re-read, so two presses or a withdrawal at
        the same moment cannot spend the same money twice. When the whole loan
        is cleared, the loan itself is marked repaid and a new one can be asked
        for.
        """
        wallet = Wallet.objects.select_for_update().get(pk=self.pk)
        if amount <= 0:
            raise ValidationError("Enter an amount to repay.")
        if wallet.loan_balance <= 0:
            raise ValidationError("You have no Ads funding to repay.")
        if amount > wallet.loan_balance:
            raise ValidationError(
                f"You owe {wallet.money(wallet.loan_balance)}. Enter that amount or less."
            )
        if amount > wallet.available_balance:
            raise ValidationError("That is more than your available balance.")

        wallet.loan_balance -= amount
        wallet.loan_repaid_total += amount
        wallet.save(update_fields=["loan_balance", "loan_repaid_total"])
        # Each repayment is its own line in the agent's earnings history.
        LoanRepayment.objects.create(agent=wallet.agent, amount=amount, currency=wallet.currency)

        if wallet.loan_balance == 0:
            wallet.agent.loans.filter(
                status__in=(Loan.Status.APPROVED, Loan.Status.DISBURSED)
            ).update(status=Loan.Status.REPAID)
        return wallet

    def credit_commission(self, kind, amount):
        """Add a commission in the database itself.

        This used to add to this copy of the wallet and save every column. A
        copy read before a withdrawal then wrote its old `total_withdrawn` back
        over the withdrawal, and the agent could take the same money twice.
        An F() update touches only the earned totals and cannot lose another
        write.
        """
        field = (
            "registration_commission_total"
            if kind == Commission.Kind.REGISTRATION
            else "visa_commission_total"
        )
        Wallet.objects.filter(pk=self.pk).update(
            **{field: F(field) + amount, "total_earned": F("total_earned") + amount}
        )
        self.refresh_from_db(fields=[field, "total_earned"])


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
    # What was added to the wallet, in the wallet's currency.
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=AGENT_COMMISSION_PER_MILESTONE
    )
    currency = models.CharField(max_length=8, default="NGN")
    # The commission as it is set, in Naira, and the rate it was converted at
    # the moment it was credited (Naira per unit; 1 for Naira).
    amount_ngn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fx_rate = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("1"))
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-earned_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("application", "kind"), name="one_commission_per_milestone"
            )
        ]
        indexes = [
            # The agent's commission list and wallet history, newest first.
            models.Index(fields=["agent", "-earned_at"], name="commission_agent_earned_idx"),
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
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    # The agent's wallet currency when the request was made.
    currency = models.CharField(max_length=8, default="NGN")
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
            # "Is a loan still owed?" is asked on every loan request.
            models.Index(fields=["agent", "status"], name="loan_agent_status_idx"),
        ]
        verbose_name = "ads funding request"
        verbose_name_plural = "ads funding requests"

    def __str__(self):
        return f"Loan {self.reference} · {self.get_status_display()}"

    @property
    def reference(self):
        return f"LN-{self.pk:05d}"


class LoanRepayment(models.Model):
    """Ads funding paid back out of the agent's balance, one row per repayment.

    The wallet keeps the running total in ``loan_repaid_total``; this is the
    dated record behind it, so the earnings history can list each one.
    """

    agent = models.ForeignKey(
        AgentProfile, on_delete=models.CASCADE, related_name="loan_repayments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="NGN")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["agent", "-created_at"], name="repayment_agent_created_idx"),
        ]
        verbose_name = "ads funding repayment"
        verbose_name_plural = "ads funding repayments"

    def __str__(self):
        return f"{self.agent} repaid {self.amount}"


def loan_block_reason(agent, wallet=None):
    """Why this agent cannot request Ads funding now, or "" if they can.

    One loan at a time: nothing new while a request is in review, while a loan
    is approved or out, or while any of it is still owed.
    """
    if agent.loans.filter(status=Loan.Status.PENDING).exists():
        return (
            "You already have a funding request in review. The desk will come back "
            "to you on that one before you can raise another."
        )
    if wallet is None:
        wallet = Wallet.objects.filter(agent=agent).first()
    owed = wallet.loan_balance if wallet else Decimal("0.00")
    if owed > 0:
        return (
            f"{wallet.money(owed)} of Ads funding is still owed. Repay it from your balance "
            "on this page, and you can request again once it is cleared."
        )
    if agent.loans.filter(status__in=(Loan.Status.APPROVED, Loan.Status.DISBURSED)).exists():
        return "Your current Ads funding has to be repaid before you can request more."
    return ""


class Withdrawal(models.Model):
    """A payout request. The agent is paid the full amount they ask for.

    `loan_deduction` is kept for payouts made when a share of each withdrawal
    went to an Ads funding loan. Nothing is deducted any more, so it is zero on
    every new payout.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "In review"
        # Handed to Paystack; waiting for Paystack to say it landed.
        SENDING = "sending", "Sending"
        PAID = "completed", "Paid out"
        FAILED = "rejected", "Failed"

    class Method(models.TextChoices):
        PAYSTACK = "paystack", "Paystack transfer"
        MANUAL = "manual", "Paid by staff"

    MIN_AMOUNT = MIN_WITHDRAWAL_NGN

    agent = models.ForeignKey(
        AgentProfile, on_delete=models.CASCADE, related_name="withdrawals"
    )
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    loan_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    # The agent's wallet currency: what the payout is to be paid in.
    currency = models.CharField(max_length=8, default="NGN")
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    # The bank account on file when the payout was requested. A later change
    # to the profile does not move a payout already asked for.
    paid_to = models.CharField(max_length=200, blank=True)
    # How it is paid: automatically through Paystack (Nigerian agents with a
    # verified account), or by staff (everyone else, and the fallback).
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.MANUAL)
    # The account the payout goes to, kept as it was when requested.
    bank_code = models.CharField(max_length=12, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    # Our reference for the Paystack transfer, unique, so Paystack never pays
    # the same payout twice; and Paystack's own transfer code.
    paystack_reference = models.CharField(max_length=40, unique=True, null=True, blank=True)
    transfer_code = models.CharField(max_length=40, blank=True)
    # Why it is waiting for staff, or why Paystack did not send it.
    review_reason = models.CharField(max_length=200, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"], name="withdrawal_status_idx"),
            models.Index(fields=["agent", "-created_at"], name="withdrawal_agent_created_idx"),
        ]
        verbose_name = "agent payout"
        verbose_name_plural = "agent payouts"

    def __str__(self):
        return f"{self.reference} · {self.amount_requested}"

    @property
    def reference(self):
        return f"WD-{self.pk:05d}"

    @transaction.atomic
    def refund_if_pending(self, reason=""):
        """Refund a payout only while it is still in review.

        Staff fail payouts from a list loaded a moment earlier. In between, the
        payout may have been handed to Paystack (Sending) or paid; refunding it
        then would give back money that has left. Locked and re-read first.
        """
        locked = type(self).objects.select_for_update().get(pk=self.pk)
        if locked.status != self.Status.PENDING:
            return False
        return self.refund(reason)

    @transaction.atomic
    def refund(self, reason=""):
        """Mark this payout failed and give the money back to the agent's wallet.

        Locked and re-read, so a payout already failed (by staff, or by a
        repeated Paystack notice) is never refunded twice. Returns whether it
        was refunded now.
        """
        locked = Withdrawal.objects.select_for_update().get(pk=self.pk)
        if locked.status == Withdrawal.Status.FAILED:
            return False
        locked.status = Withdrawal.Status.FAILED
        if reason:
            locked.failure_reason = reason[:300]
        locked.save(update_fields=["status", "failure_reason"])
        wallet = Wallet.objects.select_for_update().get(agent_id=locked.agent_id)
        wallet.total_withdrawn = max(Decimal("0.00"), wallet.total_withdrawn - locked.amount_requested)
        wallet.loan_balance += locked.loan_deduction
        wallet.save(update_fields=["total_withdrawn", "loan_balance"])
        self.status, self.failure_reason = locked.status, locked.failure_reason
        return True

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

        from .payout_account import check_withdrawal_hold

        check_withdrawal_hold(agent)
        # The minimum is set in Naira and applied in the wallet's currency.
        minimum = wallet.minimum_withdrawal
        if amount < minimum:
            raise ValidationError(
                f"The smallest withdrawal is {wallet.money(minimum)}."
            )
        if amount > wallet.available_balance:
            raise ValidationError("That is more than your available balance.")

        from .payout_account import destination_label

        withdrawal = cls.objects.create(
            agent=agent,
            amount_requested=amount,
            net_amount=amount,
            currency=wallet.currency,
            paid_to=destination_label(agent),
        )

        wallet.total_withdrawn += amount
        wallet.save(update_fields=["total_withdrawn"])
        return withdrawal


class SupervisorWithdrawal(models.Model):
    """A sales manager asking for their bonus balance to be paid out.

    Simpler than the agent equivalent: there is no ad-funding loan to repay, so
    the amount requested is the amount sent. Raising one moves the balance
    straight away, which is what stops the same money being requested twice
    while the first payout is still being processed.
    """

    # The same statuses and methods as an agent payout (Withdrawal), so one
    # set of payout rules serves both (see payouts.py).
    Status = Withdrawal.Status
    Method = Withdrawal.Method

    MIN_AMOUNT = MIN_SUPERVISOR_WITHDRAWAL_NGN

    supervisor = models.ForeignKey(
        SupervisorProfile, on_delete=models.CASCADE, related_name="withdrawals"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    # See Withdrawal.paid_to.
    paid_to = models.CharField(max_length=200, blank=True)
    # See the matching fields on Withdrawal.
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.MANUAL)
    bank_code = models.CharField(max_length=12, blank=True)
    account_number = models.CharField(max_length=10, blank=True)
    paystack_reference = models.CharField(max_length=40, unique=True, null=True, blank=True)
    transfer_code = models.CharField(max_length=40, blank=True)
    review_reason = models.CharField(max_length=200, blank=True)
    failure_reason = models.CharField(max_length=300, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # The amount sent: a sales manager receives exactly what they asked for.
    @property
    def net_amount(self):
        return self.amount

    @property
    def amount_requested(self):
        return self.amount

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            # The desk's payout queue is filtered by status.
            models.Index(fields=["status"], name="mgr_withdrawal_status_idx"),
            models.Index(fields=["supervisor", "-created_at"], name="mgr_withdrawal_created_idx"),
        ]
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

        from .payout_account import check_withdrawal_hold

        check_withdrawal_hold(locked)
        if amount < MIN_SUPERVISOR_WITHDRAWAL_NGN:
            raise ValidationError(
                f"The smallest withdrawal is ₦{MIN_SUPERVISOR_WITHDRAWAL_NGN:,.0f}."
            )
        if amount > locked.available_balance:
            raise ValidationError("That is more than your available balance.")

        from .payout_account import destination_label

        withdrawal = cls.objects.create(
            supervisor=locked, amount=amount, paid_to=destination_label(locked)
        )
        locked.total_withdrawn += amount
        locked.save(update_fields=["total_withdrawn"])
        supervisor.total_withdrawn = locked.total_withdrawn
        return withdrawal

    @transaction.atomic
    def mark_failed(self):
        """Give the money back. A payout that never left has to be returned.

        Only a pending payout can be failed by staff, and the row is locked and
        re-read first, so two clicks, or a payout already marked paid, never
        refund twice.
        """
        locked = type(self).objects.select_for_update().get(pk=self.pk)
        if locked.status != self.Status.PENDING:
            return False
        return self.refund("Marked as failed by staff.")

    @transaction.atomic
    def refund(self, reason=""):
        """Mark failed and return the money, once (see Withdrawal.refund)."""
        locked = type(self).objects.select_for_update().get(pk=self.pk)
        if locked.status == self.Status.FAILED:
            return False
        locked.status = self.Status.FAILED
        if reason:
            locked.failure_reason = reason[:300]
        locked.save(update_fields=["status", "failure_reason"])
        self.status, self.failure_reason = locked.status, locked.failure_reason

        supervisor = SupervisorProfile.objects.select_for_update().get(pk=self.supervisor_id)
        supervisor.total_withdrawn = max(
            Decimal("0.00"), supervisor.total_withdrawn - locked.amount
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


def contract_upload_path(instance, filename):
    from apps.applications.uploads import _stored_name

    return _stored_name("contracts", filename)


class AgentContract(models.Model):
    """An agent's signed Sales Partnership Contract.

    Either signed in the portal (the PDF is built from the company's template
    with the agent's details and signature on it, see contract_pdf.py), or a
    paper contract signed before the portal had a contract page, uploaded by
    staff. Once there is a file, the agent can view and download it.
    """

    class Source(models.TextChoices):
        PORTAL = "portal", "Signed in the portal"
        UPLOADED = "uploaded", "Uploaded by staff"

    class Method(models.TextChoices):
        DRAWN = "drawn", "Drawn"
        TYPED = "typed", "Typed name"

    agent = models.OneToOneField(AgentProfile, on_delete=models.CASCADE, related_name="contract")
    file = models.FileField(upload_to=contract_upload_path, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOADED)
    signed_on = models.DateField(null=True, blank=True, help_text="The date on the contract.")
    signed_at = models.DateTimeField(null=True, blank=True)
    # What was written on the contract, kept as it was on the day.
    signer_name = models.CharField(max_length=180, blank=True)
    signer_email = models.EmailField(blank=True)
    signer_phone = models.CharField(max_length=40, blank=True)
    signer_address = models.CharField(max_length=255, blank=True)
    signature_method = models.CharField(max_length=8, choices=Method.choices, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    ngn_per_unit = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "partnership contract"
        verbose_name_plural = "partnership contracts"

    def __str__(self):
        return f"Contract: {self.agent}"

    @property
    def filename(self):
        import os

        extension = os.path.splitext(self.file.name or "")[1].lower() or ".pdf"
        return f"Apply-Gabstep-Sales-Partnership-Contract-{self.agent.partner_code}{extension}"

    CONTENT_TYPES = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }

    @property
    def content_type(self):
        import os

        extension = os.path.splitext(self.file.name or "")[1].lower()
        return self.CONTENT_TYPES.get(extension, "application/octet-stream")
