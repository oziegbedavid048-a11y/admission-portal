import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.applications.constants import APPLICATION_FEE_NGN
from apps.applications import services
from apps.applications.models import Application
from apps.applications.serializers import ApplicationSerializer
from apps.applications.uploads import validate_upload
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
            "institution_fee_currency": institution.application_fee_currency if institution else "",
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
        "institution_fee_currency": institution.application_fee_currency,
        "waived": False,
    }


def _price(payment, quote):
    """Write the quoted amounts onto a payment."""
    payment.currency = quote["currency"]
    payment.symbol = quote["symbol"]
    payment.amount = quote["amount"]
    payment.processing_fee = quote["processing_fee"]
    payment.amount_ngn = quote["amount_ngn"]
    payment.processing_fee_ngn = quote["processing_fee_ngn"]
    payment.fx_rate = quote["fx_rate"]


def payer_email(application):
    """Who Paystack emails the receipt to.

    A student an agent registered is never contacted, so for those files the
    agent's own address is used.
    """
    agent = application.submitted_by_agent
    if agent is not None and agent.user.email:
        return agent.user.email
    return application.email


def company_accounts():
    """Every company account a transfer can go to, complete ones only."""
    return [
        dict(account)
        for account in getattr(settings, "COMPANY_ACCOUNTS", [])
        if account.get("bank") and account.get("account_number") and account.get("beneficiary")
    ]


def transfer_allowed(application):
    """Whether this payer may pay by bank transfer.

    Only payers in Nigeria. For a file an agent registered that is the country
    the agent signed up with; otherwise the applicant's own country of origin.
    Everyone else pays with Paystack and is never shown account details.
    """
    country = getattr(settings, "TRANSFER_COUNTRY", "Nigeria").strip().lower()
    agent = application.submitted_by_agent
    if agent is not None:
        payer_country = agent.user.country
    else:
        payer_country = application.origin_country.name if application.origin_country else ""
    return bool(company_accounts()) and (payer_country or "").strip().lower() == country


def transfer_account():
    """The first company account, for the applicant checkout's fallback text."""
    accounts = company_accounts()
    return accounts[0] if accounts else None


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
        allowed = transfer_allowed(application)
        quote["paystack_available"] = gateway.is_live()
        quote["transfer_allowed"] = allowed
        # Account numbers go only to payers who may transfer.
        quote["transfer_accounts"] = company_accounts() if allowed else []
        quote["transfer_account"] = transfer_account() if allowed else None
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
        try:
            serializer = CheckoutSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Only a file the caller may already see: their own, a student they
            # filed, or any file for staff. Someone else's reference is "not
            # found", exactly as if it did not exist, so it cannot be used to
            # read that file or to reset its payment.
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

            if existing and existing.status == Payment.Status.REVIEW:
                # A transfer receipt is already with the desk. Starting a card
                # payment on top of it could take the fee twice.
                return Response(
                    {"detail": "A bank transfer for this student is waiting for confirmation."},
                    status=status.HTTP_409_CONFLICT,
                )

            quote = quote_for(application)
            payment = existing or Payment(application=application)
            _price(payment, quote)
            payment.gateway = Payment.Gateway.PAYSTACK
            payment.status = Payment.Status.PENDING
            payment.save()

            if quote["waived"]:
                payment.mark_waived()
                services.sync_payment_checkpoint(application)
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
                application = Application.objects.get(pk=application.pk)
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
            frontend_base = getattr(settings, "FRONTEND_URL", "").rstrip("/")
            origin = request.headers.get("Origin") or request.headers.get("Referer")
            if origin and ("localhost" in frontend_base or not frontend_base):
                from urllib.parse import urlparse
                p = urlparse(origin)
                if p.scheme and p.netloc:
                    frontend_base = f"{p.scheme}://{p.netloc}"
            elif request.headers.get("X-Forwarded-Host") and ("localhost" in frontend_base or not frontend_base):
                proto = request.headers.get("X-Forwarded-Proto", "https")
                host = request.headers.get("X-Forwarded-Host")
                frontend_base = f"{proto}://{host}"

            if serializer.validated_data["return_to"] == "agent":
                callback_url = f"{frontend_base}/agent/payment/{application.reference}"
            else:
                callback_url = f"{frontend_base}/payment/{application.reference}"

            authorization_url = gateway.initiate(
                payment,
                email=payer_email(application),
                callback_url=callback_url,
            )

            services.notify(
                application,
                f"Application fee of {payment.display_total} is outstanding. Your file "
                "is with the admissions desk and moves on once the fee clears.",
                send_email=False,
            )

            application = Application.objects.get(pk=application.pk)
            return Response(
                {
                    "payment": PaymentSerializer(payment).data,
                    "application": ApplicationSerializer(application).data,
                    # Present when a provider is configured: send the applicant here.
                    "authorization_url": authorization_url,
                    # When it is not, this is how the money is expected to arrive.
                    "pay_by_transfer": authorization_url is None,
                    "transfer_account": (
                        transfer_account()
                        if authorization_url is None and transfer_allowed(application)
                        else None
                    ),
                    "waived": False,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            import logging, traceback
            from rest_framework.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                raise
            logging.getLogger(__name__).error("Checkout error: %s\n%s", exc, traceback.format_exc())
            return Response(
                {"detail": f"Checkout error: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TransferReceiptView(APIView):
    """Record a bank transfer: the payer says they sent it and attaches the receipt.

    Does not settle anything. The payment waits as "Awaiting confirmation" until
    staff confirm the money arrived, and only then is any commission paid.
    """

    throttle_classes = (PaymentThrottle,)
    parser_classes = (MultiPartParser, FormParser)

    @transaction.atomic
    def post(self, request, reference):
        application = visible_applications(request.user).filter(reference=reference).first()
        if application is None:
            return Response({"detail": "No such application."}, status=status.HTTP_404_NOT_FOUND)
        if not transfer_allowed(application):
            return Response(
                {"detail": "Bank transfer is only available in Nigeria. Pay with Paystack."},
                status=status.HTTP_403_FORBIDDEN,
            )
        bank = next(
            (account for account in company_accounts() if account["id"] == request.data.get("bank")),
            None,
        )
        if bank is None:
            return Response({"bank": ["Choose the bank you sent the money to."]}, status=status.HTTP_400_BAD_REQUEST)

        receipt = request.FILES.get("receipt")
        if receipt is None:
            return Response({"receipt": ["Upload the transfer receipt."]}, status=status.HTTP_400_BAD_REQUEST)
        validate_upload(receipt, settings.MAX_UPLOAD_SIZE_MB)

        existing = getattr(application, "payment", None)
        if existing and existing.status in {Payment.Status.PAID, Payment.Status.WAIVED}:
            return Response(
                {"detail": "This application fee is already settled."}, status=status.HTTP_409_CONFLICT
            )

        quote = quote_for(application)
        if quote["waived"]:
            return Response(
                {"detail": "This university does not charge an application fee."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = existing or Payment(application=application)
        _price(payment, quote)
        # A transfer carries no gateway fee.
        payment.processing_fee = Decimal("0.00")
        payment.processing_fee_ngn = Decimal("0.00")
        payment.gateway = Payment.Gateway.TRANSFER
        payment.status = Payment.Status.REVIEW
        payment.receipt = receipt
        payment.receipt_submitted_at = timezone.now()
        payment.transfer_bank = f"{bank['bank']} · {bank['account_number']}"
        payment.review_note = ""
        payment.save()

        services.notify(
            application,
            f"Bank transfer of {payment.display_total} received for review. "
            "We confirm it once the money reaches our account.",
            send_email=False,
        )
        return Response({"payment": PaymentSerializer(payment).data}, status=status.HTTP_201_CREATED)


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
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (PaymentThrottle,)

    def get(self, request, reference):
        """Report a payment, and settle it if Paystack says the money is in.

        Reachable without a session, because the applicant comes back from
        Paystack on a fresh page load and is deliberately not signed in: the
        password was only ever emailed to them. An application reference is short
        enough to guess, so an unauthenticated caller has to also present the
        gateway reference Paystack appended to the return URL, and gets only
        whether the fee is settled and for how much.

        This never issues a session. It used to, and that put somebody straight
        into a dashboard for an account whose password had been emailed rather
        than chosen, which is not a sign-in anybody performed.
        """
        if request.user.is_authenticated:
            application = visible_applications(request.user).filter(
                reference=reference
            ).first()
        else:
            application = Application.objects.filter(reference=reference).first()

        if application is None or not hasattr(application, "payment"):
            return Response(
                {"detail": "No payment for this application."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = application.payment

        if not request.user.is_authenticated:
            supplied = (request.query_params.get("reference") or "").strip()
            if not supplied or supplied != payment.gateway_reference:
                # Wrong or missing: answer exactly as for an unknown reference, so
                # nothing is learned by guessing application numbers.
                return Response(
                    {"detail": "No payment for this application."},
                    status=status.HTTP_404_NOT_FOUND,
                )

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

        is_settled = payment.status in {Payment.Status.PAID, Payment.Status.WAIVED}

        if request.user.is_authenticated:
            return Response(
                {
                    "payment": PaymentSerializer(payment).data,
                    "settled": is_settled,
                    "settled_now": settled_now,
                }
            )

        # Enough to show a confirmation, and nothing that identifies anybody.
        return Response(
            {
                "settled": is_settled,
                "settled_now": settled_now,
                "display_total": payment.display_total,
                "application": application.reference,
                # Whether the login has actually gone out, so the page can tell
                # the applicant to check their inbox or to contact the desk.
                "credentials_sent": bool(application.welcome_email_sent),
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
