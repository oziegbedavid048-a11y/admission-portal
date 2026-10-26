"""Payment records for the application fee.

The gateway integration is deliberately behind one seam: ``Payment.initiate``
records the intent and ``Payment.mark_paid`` settles it. Swapping the simulated
provider for a live Paystack or Flutterwave call means calling their API in the
view and then calling ``mark_paid`` with the real reference, and nothing else in
the project needs to change.
"""

import secrets
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.applications.uploads import receipt_upload_path


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        # A bank transfer the payer says they have made, with a receipt. It
        # waits here until staff confirm the money arrived.
        REVIEW = "review", "Awaiting confirmation"
        PAID = "paid", "Paid"
        # Pay small small: the deposit (and perhaps an instalment) is in, the
        # rest is still to come. Work on the file starts here; the agent's
        # commission waits for Paid.
        PART_PAID = "part_paid", "Part paid"
        WAIVED = "waived", "Waived (partner)"
        FAILED = "failed", "Failed"

    class Plan(models.TextChoices):
        FULL = "full", "Pay in full"
        INSTALMENTS = "instalments", "Pay small small"

    class Gateway(models.TextChoices):
        PAYSTACK = "Paystack", "Paystack"
        FLUTTERWAVE = "Flutterwave", "Flutterwave"
        TRANSFER = "Bank transfer", "Bank transfer"
        WAIVER = "Institutional Waiver", "Institutional waiver"
        PARTNER = "Agent Payout / Verified Partner", "Partner payout"

    application = models.OneToOneField(
        "applications.Application", on_delete=models.CASCADE, related_name="payment"
    )
    reference = models.CharField(max_length=32, unique=True, editable=False)
    gateway = models.CharField(
        max_length=40, choices=Gateway.choices, default=Gateway.PAYSTACK
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )

    # What the applicant was actually charged, in their own currency.
    currency = models.CharField(max_length=8, default="NGN")
    symbol = models.CharField(max_length=8, default="₦")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    processing_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    # The same charge in Naira, kept so the books reconcile whatever the
    # display currency and whatever the rate did afterwards. This is the
    # application fee alone.
    amount_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    # The gateway's own cut, in Naira. Held separately from `processing_fee`,
    # which is the same figure converted for display, so the amount the card is
    # debited is never derived from a converted number.
    processing_fee_ngn = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    fx_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1"))

    # The reference the gateway knows this attempt by.
    #
    # Separate from `reference` because Paystack refuses a reference it has seen
    # before. A first attempt that is abandoned or declined has already burned
    # ours, so a retry needs a new one while the payment, the receipt and the
    # application all keep pointing at the same row.
    gateway_reference = models.CharField(max_length=64, blank=True, db_index=True)

    # A bank transfer: the receipt the payer uploaded, when, and why staff
    # turned it down if they did.
    receipt = models.FileField(upload_to=receipt_upload_path, blank=True, null=True)
    receipt_submitted_at = models.DateTimeField(null=True, blank=True)
    # Which company account the payer says they sent the money to.
    transfer_bank = models.CharField(max_length=80, blank=True)
    review_note = models.TextField(blank=True, max_length=1000)

    # How the fee is being paid, and how much of `amount_ngn` is in so far.
    plan = models.CharField(max_length=12, choices=Plan.choices, default=Plan.FULL)
    paid_ngn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    # When the deposit landed: instalments fall due a week, then two, after it.
    deposit_paid_at = models.DateTimeField(null=True, blank=True)
    # Reminders already sent, as "<instalment>:<kind>", so none goes twice.
    reminders_sent = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"], name="payment_status_idx"),
        ]
        verbose_name = "application fee"
        verbose_name_plural = "application fees"

    def __str__(self):
        return f"{self.reference} · {self.display_total} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"GBS-{secrets.token_hex(6).upper()}"
        super().save(*args, **kwargs)

    @property
    def total(self):
        """What the applicant sees, in their own currency."""
        return self.amount + self.processing_fee

    @property
    def balance_ngn(self):
        """What is still owed on the fee, in Naira. Nothing once paid or waived."""
        if self.status in (self.Status.PAID, self.Status.WAIVED):
            return Decimal("0.00")
        return max(Decimal("0.00"), Decimal(self.amount_ngn) - Decimal(self.paid_ngn or 0))

    @property
    def total_ngn(self):
        """What the card is actually debited. The gateway is asked for this."""
        return self.amount_ngn + self.processing_fee_ngn

    def new_gateway_reference(self):
        """A reference this attempt can be initialised with.

        Suffixed rather than random so a settlement report still reads back to
        the payment it belongs to.
        """
        attempt = 1
        if self.gateway_reference and "-A" in self.gateway_reference:
            try:
                attempt = int(self.gateway_reference.rsplit("-A", 1)[1]) + 1
            except ValueError:
                attempt = 2
        elif self.gateway_reference:
            attempt = 2
        self.gateway_reference = f"{self.reference}-A{attempt}"
        return self.gateway_reference

    @property
    def display_total(self):
        """"€120.00", or "GMD 1,650.00" for a currency with no sign on file."""
        sign = (self.symbol or "").strip()
        if sign and sign.upper() != (self.currency or "").upper():
            return f"{sign}{self.total:,.2f}"
        return f"{self.currency} {self.total:,.2f}"

    def mark_paid(self, gateway=None):
        if gateway:
            self.gateway = gateway
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["gateway", "status", "paid_at"])
        return self

    def mark_waived(self):
        self.status = self.Status.WAIVED
        self.gateway = self.Gateway.WAIVER
        self.amount = Decimal("0.00")
        self.processing_fee = Decimal("0.00")
        self.processing_fee_ngn = Decimal("0.00")
        self.paid_at = timezone.now()
        self.save()
        return self



class PaymentCharge(models.Model):
    """One amount asked for and, once confirmed, received against a fee.

    A fee paid in full is one charge; pay small small is a deposit and then
    instalments, or the balance at once. Each Paystack attempt and each bank
    transfer receipt is a row, created before any money moves, holding what it
    was for. Settlement applies a row once (the row is locked and its status
    checked), so a repeated webhook can never count the same money twice, and
    an attempt the payer abandoned and later completed is still counted at the
    amount it was opened for.
    """

    class Kind(models.TextChoices):
        FULL = "full", "Full fee"
        DEPOSIT = "deposit", "Deposit"
        INSTALMENT = "instalment", "Instalment"
        BALANCE = "balance", "Balance"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for payment"
        REVIEW = "review", "Transfer awaiting confirmation"
        PAID = "paid", "Received"
        FAILED = "failed", "Not received"

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="charges")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    # What this charge pays off the fee, and what the payer was asked for in
    # total (the same, plus a gateway fee when the site adds one).
    amount_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    expected_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    gateway = models.CharField(max_length=40, choices=Payment.Gateway.choices)
    # The Paystack attempt reference; empty for a bank transfer.
    gateway_reference = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=["payment", "status"], name="charge_payment_status_idx")]
        verbose_name = "fee payment"
        verbose_name_plural = "fee payments"

    def __str__(self):
        return f"{self.get_kind_display()} ₦{self.amount_ngn:,.0f} ({self.get_status_display()})"


def _link_code():
    return secrets.token_urlsafe(24)


class PaymentLink(models.Model):
    """A link an agent sends a student so the student pays the fee themselves.

    For students outside Nigeria, who cannot use the company's Nigerian bank
    accounts: the student opens the link on their own phone and pays by card
    through Paystack. Settlement is the same as any Paystack payment (the
    signed webhook, or the return page asking Paystack), so the file shows as
    paid and the agent's commission is credited the moment Paystack confirms.

    The code is the only thing that opens the page, so it is long and random.
    One link per application; asking again returns the same link.
    """

    application = models.OneToOneField(
        "applications.Application", on_delete=models.CASCADE, related_name="payment_link"
    )
    code = models.CharField(max_length=48, unique=True, default=_link_code, editable=False)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "student payment link"
        verbose_name_plural = "student payment links"

    def __str__(self):
        return f"Payment link for {self.application.reference}"


class PaymentToConfirm(Payment):
    """Bank transfers waiting for staff to confirm the money arrived.

    A proxy so the admin can give this one job its own screen.
    """

    class Meta:
        proxy = True
        verbose_name = "payment to confirm"
        verbose_name_plural = "payments to confirm"
