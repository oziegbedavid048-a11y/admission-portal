"""Payment links: an agent sends one to a student, and the student pays.

Made for students outside Nigeria. They cannot transfer to the company's
Nigerian bank accounts, and the agent should not have to carry their money.
So the agent creates a link from the fee step and sends it (WhatsApp, SMS);
the student opens it on their own phone and pays by card through Paystack.

Nothing about settlement is new. The student's payment is an ordinary
Paystack payment on the application's own Payment row, so it is settled by the
signed webhook or by this page asking Paystack on the way back, through
`settle()`, which is also what credits the agent's commission. The moment
Paystack confirms, the file shows as paid in the agent's portal and the
commission is in their wallet, exactly as when the agent pays.

Paystack's own card fee is added on Paystack's page ("pass charges to
customer"), so the student pays it, including the higher fee on a foreign card.

The page is public: whoever holds the link can see what it is for and pay it.
So it shows only what a payer needs (the school, the courses, the fee, the
student's first name) and never contact details, and the code is long and
random so it cannot be guessed.
"""

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.models import Application
from apps.applications.views import visible_applications
from config.throttles import CheckoutThrottle, EdgeThrottle, PaymentStatusThrottle, UserThrottle

from . import gateway
from .models import Payment, PaymentLink
from .settlement import settle
from .views import ALREADY_CONFIRMED, _price, fee_already_confirmed, payer_email, quote_for

logger = logging.getLogger(__name__)

SETTLED = {Payment.Status.PAID, Payment.Status.WAIVED}
NOT_FOUND = "This payment link is not valid. Ask the person who sent it for a new one."


def local_estimate(application, total_ngn):
    """The fee in the student's own currency, for a student outside Nigeria.

    The card is charged in Naira; the student's bank converts it. So this is
    what they can expect to see on their statement, at today's rate (the live
    rate, or the admin's Exchange rates table when the provider is down), the
    same rate agent wallets use. Nothing is shown when no rate is on file.
    """
    from apps.partners.currency import from_naira, money

    country = application.origin_country
    currency = ((country.currency if country else "") or "NGN").strip().upper()
    if currency == "NGN":
        return {}
    try:
        amount, _rate = from_naira(total_ngn, currency)
    except (ValueError, ArithmeticError):
        logger.warning("No exchange rate for %s; payment link shows the fee without it.", currency)
        return {}
    return {
        "local_currency": currency,
        "local_amount": amount,
        "local_display": money(amount, currency, (country.symbol or "").strip() or None),
        "country": country.name,
    }


def link_url(link):
    base = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    return f"{base}/pay/{link.code}"


def standing(application):
    """Where this fee stands: "paid", "review", "no_fee" or "due"."""
    payment = getattr(application, "payment", None)
    if payment is not None and payment.status in SETTLED:
        return "paid"
    if fee_already_confirmed(application):
        return "paid"
    if payment is not None and payment.status == Payment.Status.REVIEW:
        return "review"
    if quote_for(application)["waived"]:
        return "no_fee"
    return "due"


REFUSALS = {
    "paid": ("This application fee has already been paid.", status.HTTP_409_CONFLICT),
    "review": (
        "A bank transfer for this application is waiting for confirmation, so it cannot be paid by card as well.",
        status.HTTP_409_CONFLICT,
    ),
    "no_fee": ("This university does not charge an application fee.", status.HTTP_400_BAD_REQUEST),
}


def _refusal(application, state):
    detail, code = REFUSALS[state]
    if state == "paid" and fee_already_confirmed(application) and not (
        getattr(application, "payment", None) and application.payment.status in SETTLED
    ):
        detail = ALREADY_CONFIRMED
    return Response({"detail": detail, "code": state}, status=code)


class PaymentLinkView(APIView):
    """The agent asks for the link to send a student. Same link every time."""

    throttle_classes = (UserThrottle, CheckoutThrottle)

    def post(self, request, reference):
        application = visible_applications(request.user).filter(reference=reference).first()
        if application is None:
            return Response({"detail": "No such application."}, status=status.HTTP_404_NOT_FOUND)
        if application.submitted_by_agent_id is None:
            return Response(
                {"detail": "Payment links are for students registered by an agent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        state = standing(application)
        if state != "due":
            return _refusal(application, state)
        if not gateway.is_live():
            return Response(
                {"detail": "Card payments are not available right now. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        link, _ = PaymentLink.objects.get_or_create(
            application=application, defaults={"created_by": request.user}
        )
        return Response({"url": link_url(link), "code": link.code})


class PublicPayView(APIView):
    """The student's page behind the link. No sign-in.

    GET says what the fee is and whether it is paid. Coming back from Paystack
    it carries Paystack's reference, and if that matches the attempt on file
    the payment is checked with Paystack and settled at once rather than
    waiting for the webhook.

    POST opens a fresh Paystack checkout and answers with where to go.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get_throttles(self):
        if self.request.method == "POST":
            return [CheckoutThrottle(), EdgeThrottle()]
        return [PaymentStatusThrottle(), EdgeThrottle()]

    def _link(self, code):
        return (
            PaymentLink.objects.select_related(
                "application__institution",
                "application__payment",
                "application__origin_country",
                "application__submitted_by_agent__user",
            )
            .prefetch_related("application__programs")
            .filter(code=code)
            .first()
        )

    def get(self, request, code):
        link = self._link(code)
        if link is None:
            return Response({"detail": NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        application = link.application
        payment = getattr(application, "payment", None)

        settled_now = False
        supplied = (request.query_params.get("reference") or "").strip()
        if (
            payment is not None
            and payment.status == Payment.Status.PENDING
            and supplied
            and supplied == payment.gateway_reference
        ):
            data = gateway.verify(payment.gateway_reference)
            if (
                gateway.transaction_is_settled(data)
                and gateway.currency_is_expected(data)
                and gateway.amount_covers(payment, (data or {}).get("amount"))
            ):
                settled_now = settle(payment, Payment.Gateway.PAYSTACK, payment.gateway_reference)
            application.refresh_from_db()

        state = standing(application)
        body = {
            "status": state,
            "settled_now": settled_now,
            "student": (application.full_name or "").strip().split(" ")[0],
            "institution": application.institution.name if application.institution else "",
            "courses": (
                [application.custom_course_name]
                if application.is_custom_course
                else [program.name for program in application.programs.all()]
            ),
            "card_available": gateway.is_live(),
        }
        payment = getattr(application, "payment", None)
        if state == "paid" and payment is not None:
            body["paid_total"] = payment.display_total
        if state == "due":
            quote = quote_for(application)
            body.update(
                {
                    "currency": quote["currency"],
                    "symbol": quote["symbol"],
                    "amount": quote["amount"],
                    "amount_ngn": quote["total_ngn"],
                }
            )
            body.update(local_estimate(application, quote["total_ngn"]))
        return Response(body)

    def post(self, request, code):
        link = self._link(code)
        if link is None:
            return Response({"detail": NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        if not gateway.is_live():
            return Response(
                {"detail": "Card payments are not available right now. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # The checks and the pending payment are written together, with the
        # payment row locked, so the agent paying in the portal and the student
        # paying from the link at the same moment never both start a charge on
        # a stale view of it. Paystack is called after the transaction, as in
        # checkout.
        try:
            with transaction.atomic():
                Payment.objects.select_for_update().filter(application_id=link.application_id).first()
                # Read again under the lock: the agent may have paid meanwhile.
                application = Application.objects.select_related("institution", "payment").get(
                    pk=link.application_id
                )
                state = standing(application)
                if state != "due":
                    return _refusal(application, state)
                payment = getattr(application, "payment", None) or Payment(application=application)
                _price(payment, quote_for(application))
                payment.gateway = Payment.Gateway.PAYSTACK
                payment.status = Payment.Status.PENDING
                payment.save()
        except IntegrityError:
            # The agent started the very first payment at the same instant.
            return Response(
                {"detail": "A payment for this application was just started. Please try again in a moment."},
                status=status.HTTP_409_CONFLICT,
            )

        authorization_url = gateway.initiate(
            payment,
            # The receipt goes to the agent: a student an agent registered is
            # never written to by Gabstep.
            email=payer_email(application),
            callback_url=link_url(link),
        )
        if not authorization_url:
            return Response(
                {"detail": "The card payment page could not be opened. Please try again in a moment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"authorization_url": authorization_url}, status=status.HTTP_201_CREATED)
