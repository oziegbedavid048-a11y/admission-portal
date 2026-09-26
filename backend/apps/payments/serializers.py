from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
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
            "fx_rate",
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
