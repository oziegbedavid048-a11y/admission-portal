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
    # display currency and whatever the rate did afterwards.
    amount_ngn = models.DecimalField(max_digits=12, decimal_places=2)
    fx_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1"))

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
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
        return self.amount + self.processing_fee

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
        self.paid_at = timezone.now()
        self.save()
        return self
