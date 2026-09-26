from django.urls import path

from .views import (
    CheckoutView,
    PaymentStatusView,
    PaystackWebhookView,
    QuoteView,
    ReceiptView,
)

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("quote/<str:reference>/", QuoteView.as_view(), name="payment-quote"),
    path("receipt/<str:reference>/", ReceiptView.as_view(), name="payment-receipt"),
    # Where the applicant lands coming back from Paystack. Asks Paystack what
    # happened rather than waiting for the webhook, and settles on the same path.
    path("status/<str:reference>/", PaymentStatusView.as_view(), name="payment-status"),
    # The provider posts here. Unauthenticated by necessity, verified by
    # signature inside the view. Keep this path out of any auth middleware and
    # out of CSRF, which DRF's APIView already is.
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
]
