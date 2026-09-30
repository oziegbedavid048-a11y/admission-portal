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


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived (partner)"
        FAILED = "failed", "Failed"

    class Gateway(models.TextChoices):
        PAYSTACK = "Paystack", "Paystack"
        FLUTTERWAVE = "Flutterwave", "Flutterwave"
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
