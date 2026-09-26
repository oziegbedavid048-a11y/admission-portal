import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.applications.constants import APPLICATION_FEE_NGN
from apps.applications import services
from apps.applications.serializers import ApplicationSerializer
from apps.applications.views import visible_applications

from . import gateway
from .fees import processing_fee_ngn
from .models import Payment
from .settlement import settle
from .serializers import CheckoutSerializer, PaymentSerializer

logger = logging.getLogger(__name__)


class PaymentThrottle(ScopedRateThrottle):
    scope = "money"


def client_ip(request):
    """The caller's address, taking the first hop of a forwarding chain.

    Only used for the optional webhook allowlist. The header is client-controlled
    where nothing strips it, which is exactly why it is not what authenticates a
    webhook: the signature is.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def find_payment(gateway_reference):
    """The payment an attempt belongs to.

    Paystack knows a payment by the reference of the attempt, which carries an
    attempt suffix because Paystack refuses a reference it has seen before. Our
    own reference is accepted too, so a payment initialised before the suffix
    existed still resolves.
    """
    if not gateway_reference:
        return None
    found = Payment.objects.filter(gateway_reference=gateway_reference).first()
    if found:
        return found
    return Payment.objects.filter(reference=str(gateway_reference).split("-A")[0]).first()


def quote_for(application):
    """What this applicant owes, in their own currency and in Naira.

    **The fee belongs to the school they chose, not to the platform.** It used to
    be one flat APPLICATION_FEE_NGN for everybody, so an applicant to UCAM, whose
    fee is 150 EUR, would have been charged the 200,000 NGN another school
    charges. The amount now comes from the institution row on this application
    and from nowhere else, which is what stops one school's fee reaching another
    school's applicant.

    Everything is computed in Naira first and converted for display, never the
    other way round, because Naira is what the card is debited.
    """
    origin = application.origin_country
    institution = application.institution

    fee_ngn = institution.application_fee_ngn if institution is not None else Decimal("0.00")

    if fee_ngn <= 0:
        return {
            "currency": origin.currency,
            "symbol": origin.symbol,
            "amount": Decimal("0.00"),
            "processing_fee": Decimal("0.00"),
            "amount_ngn": Decimal("0.00"),
            "processing_fee_ngn": Decimal("0.00"),
            "total_ngn": Decimal("0.00"),
            "fx_rate": origin.ngn_per_unit,
            "institution": institution.name if institution else "",
            "institution_fee": Decimal("0.00"),
            "institution_fee_currency": institution.currency if institution else "",
            "waived": True,
        }

    gateway_fee_ngn = processing_fee_ngn(fee_ngn)
    return {
        "currency": origin.currency,
        "symbol": origin.symbol,
        "amount": origin.convert_from_ngn(fee_ngn),
        "processing_fee": origin.convert_from_ngn(gateway_fee_ngn),
        "amount_ngn": fee_ngn,
        "processing_fee_ngn": gateway_fee_ngn,
        "total_ngn": fee_ngn + gateway_fee_ngn,
        "fx_rate": origin.ngn_per_unit,
        # Stated so the applicant can see whose fee this is and what the school
        # itself calls it, rather than only the converted number.
        "institution": institution.name,
        "institution_fee": institution.application_fee,
        "institution_fee_currency": institution.currency,
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
        # Stated alongside the converted total so the applicant can see the figure
        # their card will actually show on the statement.
        quote["total_charged_ngn"] = quote["total_ngn"]
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
        payment.processing_fee_ngn = quote["processing_fee_ngn"]
        payment.fx_rate = quote["fx_rate"]
        payment.status = Payment.Status.PENDING
        payment.save()

        if quote["waived"]:
            payment.mark_waived()
            reason = (
                "Application fee waived for custom course review."
                if getattr(application, "is_custom_course", False)
                else "Application fee waived by the partner institution."
            )
            services.notify(
                application,
                reason,
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

        # Paystack sends the applicant back here. The application reference is in
        # the path so the page knows what to ask about without trusting the
        # transaction reference Paystack appends to the query string.
        authorization_url = gateway.initiate(
            payment,
            email=application.email,
            callback_url=(
                f"{settings.FRONTEND_URL.rstrip('/')}/payment/{application.reference}"
            ),
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
    """Paystack telling us money arrived.

    Unauthenticated by necessity, because Paystack holds no account here. The
    signature over the raw body is the authentication; the amount and currency are
    checked against what was quoted. Anything that fails a check is logged and
    ignored.

    Always answers 200. Paystack retries anything else, and a sender that guessed
    wrong must not be told whether it guessed right.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = ()

    def post(self, request):
        ok = Response(status=status.HTTP_200_OK)

        if not gateway.ip_is_allowed(client_ip(request)):
            logger.warning("Webhook from an address outside the allowlist.")
            return ok

        if not gateway.signature_is_valid(
            request.body, request.headers.get("x-paystack-signature", "")
        ):
            logger.warning("Rejected a webhook with an invalid signature.")
            return ok

        try:
            event = json.loads(request.body.decode())
        except (UnicodeDecodeError, ValueError):
            logger.warning("Rejected a webhook whose body was not JSON.")
            return ok

        if event.get("event") != "charge.success":
            # Every other event is recorded and otherwise ignored, so a new event
            # type from Paystack can never be mistaken for a settlement.
            logger.info("Ignoring webhook event %r.", event.get("event"))
            return ok

        data = event.get("data") or {}
        payment = find_payment(data.get("reference"))
        if payment is None:
            logger.warning("Webhook for an unknown reference %r.", data.get("reference"))
            return ok

        if not gateway.transaction_is_settled(data):
            logger.info(
                "Webhook for %s reported status %r, not success.",
                payment.reference, data.get("status"),
            )
            return ok

        if not gateway.currency_is_expected(data):
            logger.error(
                "Webhook for %s was in %r, not NGN.", payment.reference, data.get("currency")
            )
            return ok

        if not gateway.amount_covers(payment, data.get("amount")):
            logger.error(
                "Webhook for %s collected %r kobo, short of the %s NGN quoted.",
                payment.reference, data.get("amount"), payment.total_ngn,
            )
            return ok

        settle(payment, Payment.Gateway.PAYSTACK, data.get("reference"))
        return ok


class PaymentStatusView(APIView):
    """Where the applicant lands coming back from Paystack.

    The webhook is the primary path, but it can be late, retried, or lost behind a
    deploy, and the applicant is standing there now. So this asks Paystack
    directly what happened to the reference rather than waiting to be told.

    It settles on the same code path as the webhook, so the two cannot disagree
    and whichever arrives first does the work. The reference comes from the
    browser, so it is never trusted: it is only used to find a payment this user
    is allowed to see, and the amount is then confirmed against Paystack.
    """

    throttle_classes = (PaymentThrottle,)

    def get(self, request, reference):
        application = visible_applications(request.user).filter(
            reference=reference
        ).first()
        if application is None or not hasattr(application, "payment"):
            return Response(
                {"detail": "No payment for this application."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = application.payment
        settled_now = False

        if payment.status == Payment.Status.PENDING and payment.gateway_reference:
            data = gateway.verify(payment.gateway_reference)
            if (
                gateway.transaction_is_settled(data)
                and gateway.currency_is_expected(data)
                and gateway.amount_covers(payment, (data or {}).get("amount"))
            ):
                settled_now = settle(
                    payment, Payment.Gateway.PAYSTACK, payment.gateway_reference
                )
            elif data and data.get("status") in {"failed", "abandoned", "reversed"}:
                logger.info(
                    "Paystack reports %s as %r; the fee stays outstanding.",
                    payment.reference, data.get("status"),
                )

        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "settled": payment.status in {Payment.Status.PAID, Payment.Status.WAIVED},
                # True only on the call that did the settling, so the interface can
                # celebrate once rather than on every poll.
                "settled_now": settled_now,
            }
        )


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
