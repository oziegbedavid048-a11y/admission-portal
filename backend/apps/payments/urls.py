from django.urls import path

from .views import CheckoutView, PaystackWebhookView, QuoteView, ReceiptView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("quote/<str:reference>/", QuoteView.as_view(), name="payment-quote"),
    path("receipt/<str:reference>/", ReceiptView.as_view(), name="payment-receipt"),
    # The provider posts here. Unauthenticated by necessity, verified by
    # signature inside the view. Keep this path out of any auth middleware and
    # out of CSRF, which DRF's APIView already is.
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
]
