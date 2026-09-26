import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.applications.constants import APPLICATION_FEE_NGN, PROCESSING_FEE
from apps.applications import services
from apps.applications.serializers import ApplicationSerializer
from apps.applications.views import visible_applications

from . import gateway
from .models import Payment
from .serializers import CheckoutSerializer, PaymentSerializer

logger = logging.getLogger(__name__)


class PaymentThrottle(ScopedRateThrottle):
    scope = "money"


def quote_for(application):
    """What this applicant owes, in their own currency.

    The fee is a fixed amount of Naira. The origin country decides the display
    currency; a fee-free partner institution waives it entirely.
    """
    origin = application.origin_country
    institution = application.institution

    if institution is not None and institution.application_fee == 0:
        return {
            "currency": origin.currency,
            "symbol": origin.symbol,
            "amount": Decimal("0.00"),
            "processing_fee": Decimal("0.00"),
            "amount_ngn": Decimal("0.00"),
            "fx_rate": origin.ngn_per_unit,
            "waived": True,
        }

    # The gateway's cut is a flat charge in whatever currency the card is
    # billed in, so it is not converted the way the fee itself is.
    return {
        "currency": origin.currency,
        "symbol": origin.symbol,
        "amount": origin.convert_from_ngn(APPLICATION_FEE_NGN),
        "processing_fee": PROCESSING_FEE,
        "amount_ngn": APPLICATION_FEE_NGN,
        "fx_rate": origin.ngn_per_unit,
        "waived": False,
    }


def transfer_account():
    """The account to transfer the fee to, or None if none is configured.

    Returned rather than rendered into the page so the numbers live in the
    environment. An incomplete set is treated as no account at all: a half-filled
    transfer instruction is worse than none.
    """
    name = getattr(settings, "PAYOUT_BANK_NAME", "")
    number = getattr(settings, "PAYOUT_BANK_ACCOUNT", "")
    beneficiary = getattr(settings, "PAYOUT_BANK_BENEFICIARY", "")
    if not (name and number and beneficiary):
        return None
    return {"bank": name, "account_number": number, "beneficiary": beneficiary}


class QuoteView(APIView):
    """What an application will cost, before anyone is charged."""

    def get(self, request, reference):
        application = visible_applications(request.user).filter(
            reference=reference
        ).first()
        if application is None:
            return Response(
                {"detail": "No such application."}, status=status.HTTP_404_NOT_FOUND
            )
        quote = quote_for(application)
        quote["total"] = quote["amount"] + quote["processing_fee"]
        # How the money is expected to arrive, so the checkout screen can say so
        # rather than printing an account number that was baked into the markup.
        quote["provider"] = "paystack" if gateway.is_live() else "transfer"
        quote["transfer_account"] = transfer_account()
        return Response(quote)


class CheckoutView(APIView):
    """Start paying the application fee. Does not settle it.

    This used to call ``mark_paid`` itself, which meant anyone who could reach
    the endpoint had the fee marked paid and, on an agent-filed application, the
    registration commission credited, with no money arriving anywhere. A browser
    cannot prove a payment, so it no longer gets to assert one.

    What happens now:

    * a fee-free institution is waived on the spot, because there is nothing to
      collect and no commission is earned on a waiver either way,
    * otherwise the payment is recorded as **pending** and, when a provider is
      configured, the applicant is handed the URL to go and pay at.

    Settlement arrives later, through the signed provider webhook or through the
    desk confirming a bank transfer in the admin. Both of those credit the
    agent's commission; nothing in this view does.
    """

    throttle_classes = (PaymentThrottle,)

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        application = visible_applications(request.user).filter(
            reference=serializer.validated_data["application"]
        ).first()
        if application is None:
            return Response(
                {"detail": "No such application."}, status=status.HTTP_404_NOT_FOUND
            )

        existing = getattr(application, "payment", None)
        if existing and existing.status in {Payment.Status.PAID, Payment.Status.WAIVED}:
            # Already settled. Saying so is not an error, and it stops a retried
            # request from opening a second charge.
            return Response(
                {"payment": PaymentSerializer(existing).data, "already_settled": True}
            )

        quote = quote_for(application)
        payment = existing or Payment(application=application)
        payment.currency = quote["currency"]
        payment.symbol = quote["symbol"]
        payment.amount = quote["amount"]
        payment.processing_fee = quote["processing_fee"]
        payment.amount_ngn = quote["amount_ngn"]
        payment.fx_rate = quote["fx_rate"]
        payment.status = Payment.Status.PENDING
        payment.save()

        if quote["waived"]:
            payment.mark_waived()
            services.notify(
                application,
                "Application fee waived by the partner institution.",
                send_email=False,
            )
            application = visible_applications(request.user).get(pk=application.pk)
            return Response(
                {
                    "payment": PaymentSerializer(payment).data,
                    "application": ApplicationSerializer(application).data,
                    "waived": True,
                },
                status=status.HTTP_201_CREATED,
            )

        authorization_url = gateway.initiate(
            payment,
            email=application.email,
            callback_url=f"{settings.FRONTEND_URL.rstrip('/')}/portal/programme",
        )

        services.notify(
            application,
            f"Application fee of {payment.display_total} is outstanding. Your file "
            "is with the admissions desk and moves on once the fee clears.",
            send_email=False,
        )

        application = visible_applications(request.user).get(pk=application.pk)
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "application": ApplicationSerializer(application).data,
                # Present when a provider is configured: send the applicant here.
                "authorization_url": authorization_url,
                # When it is not, this is how the money is expected to arrive.
                "pay_by_transfer": authorization_url is None,
                "transfer_account": None if authorization_url else transfer_account(),
                "waived": False,
            },
            status=status.HTTP_201_CREATED,
        )


class PaystackWebhookView(APIView):
    """The only door a payment can be settled through without a human.

    Unauthenticated by necessity, because the provider holds no account here. The
    signature is the authentication, and the amount is checked against what was
    quoted. Anything failing either check is logged and ignored.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = ()

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not gateway.signature_is_valid(request.body, signature):
            logger.warning("Rejected a payment webhook with an invalid signature.")
            # 200 so a sender is never told whether it guessed correctly.
            return Response(status=status.HTTP_200_OK)

        try:
            event = json.loads(request.body.decode())
        except (UnicodeDecodeError, ValueError):
            return Response(status=status.HTTP_200_OK)

        if event.get("event") != "charge.success":
            return Response(status=status.HTTP_200_OK)

        data = event.get("data") or {}
        reference = data.get("reference")
        payment = Payment.objects.filter(reference=reference).first()
        if payment is None:
            logger.warning("Payment webhook for an unknown reference %r.", reference)
            return Response(status=status.HTTP_200_OK)

        if payment.status in {Payment.Status.PAID, Payment.Status.WAIVED}:
            # Providers retry. Settling twice would pay the commission twice.
            return Response(status=status.HTTP_200_OK)

        if not gateway.amount_matches(payment, data.get("amount")):
            logger.error(
                "Payment %s came back settled for %r, short of the %s quoted.",
                payment.reference,
                data.get("amount"),
                payment.amount_ngn,
            )
            return Response(status=status.HTTP_200_OK)

        self._settle(payment)
        return Response(status=status.HTTP_200_OK)

    @transaction.atomic
    def _settle(self, payment):
        payment.mark_paid(Payment.Gateway.PAYSTACK)
        services.notify(
            payment.application,
            f"Payment of {payment.display_total} confirmed. "
            "Your receipt is ready to download.",
        )
        # One of the two places a paid fee earns the agent their first
        # commission. The other is the desk confirming a transfer in the admin.
        services.award_registration_commission(payment.application)


class ReceiptView(APIView):
    """The numbers the printable receipt prints."""

    def get(self, request, reference):
        application = visible_applications(request.user).filter(
            reference=reference
        ).first()
        if application is None or not hasattr(application, "payment"):
            return Response(
                {"detail": "No receipt for this application yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payment = application.payment
        return Response(
            {
                "reference": payment.reference,
                "application_reference": application.reference,
                "paid_at": payment.paid_at,
                "full_name": application.full_name,
                "email": application.email,
                "institution": application.institution.name
                if application.institution
                else "",
                "gateway": payment.gateway,
                "amount": payment.total,
                "currency": payment.currency,
                "display_total": payment.display_total,
                "status": payment.status,
            }
        )
