from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    # What the card is actually debited. Exposed beside the converted figures so
    # a receipt can state the number that will appear on the statement.
    total_ngn = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    display_total = serializers.CharField(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "reference",
            "gateway",
            "status",
            "currency",
            "symbol",
            "amount",
            "processing_fee",
            "total",
            "display_total",
            "amount_ngn",
            "processing_fee_ngn",
            "total_ngn",
            "fx_rate",
            "review_note",
            "receipt_submitted_at",
            "transfer_bank",
            "created_at",
            "paid_at",
        )
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    """Settle the fee for an application that has just been submitted."""

    application = serializers.CharField(help_text="Application reference.")
    gateway = serializers.ChoiceField(
        choices=Payment.Gateway.choices, default=Payment.Gateway.PAYSTACK
    )
    # Where Paystack sends the payer back to: the applicant's page, or the
    # agent portal when an agent paid for a student.
    return_to = serializers.ChoiceField(choices=("portal", "agent"), default="portal")
