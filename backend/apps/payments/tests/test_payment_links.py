"""Payment links: an agent sends one, the student pays, the agent is paid.

The student's payment is an ordinary Paystack payment on the application, so
the file shows as paid and the agent's commission is credited the moment
Paystack confirms it, by webhook or by the page asking Paystack on return.
"""

import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications.tests.factories import make_application, make_user
from apps.catalog.models import DestinationCountry, Institution
from apps.partners.models import AgentProfile, Commission, Wallet
from apps.payments.fees import minor_units
from apps.payments.models import Payment, PaymentLink

KEY = "sk_test_simulated"
AUTH_URL = "https://checkout.paystack.test/abc"


@override_settings(PAYSTACK_SECRET_KEY=KEY, FRONTEND_URL="https://apply.example.com")
class PaymentLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        canada = DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        self.school = Institution.objects.create(
            slug="maple", name="Maple College", country=canada,
            application_fee=Decimal("5000"), application_fee_currency="NGN",
        )
        self.agent_user = make_user("agent@example.com", role=User.Role.AGENT, full_name="Ada Agent")
        self.agent = AgentProfile.objects.create(user=self.agent_user)
        Wallet.objects.create(agent=self.agent)
        student = make_user("kwame@example.com", full_name="Kwame Mensah")
        self.application = make_application(
            student, institution=self.school, submitted_by_agent=self.agent,
            full_name="Kwame Mensah", phone="+233200000000",
        )
        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agent_user)
        self.public = APIClient()

    # ── The agent creates the link ────────────────────────────────────

    def create_link(self, client=None):
        return (client or self.agent_client).post(f"/api/payments/link/{self.application.reference}/")

    def test_the_agent_gets_one_link_for_the_student(self):
        first = self.create_link()
        self.assertEqual(first.status_code, 200, first.content)
        code = PaymentLink.objects.get(application=self.application).code
        self.assertEqual(first.json()["url"], f"https://apply.example.com/pay/{code}")
        self.assertGreaterEqual(len(code), 30)
        # Asking again gives the same link, so one sent earlier keeps working.
        self.assertEqual(self.create_link().json()["url"], first.json()["url"])
        self.assertEqual(PaymentLink.objects.count(), 1)

    def test_another_agent_cannot_make_a_link_for_this_student(self):
        other = make_user("other@example.com", role=User.Role.AGENT)
        AgentProfile.objects.create(user=other)
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(self.create_link(client).status_code, 404)
        self.assertFalse(PaymentLink.objects.exists())

    def test_an_applicants_own_file_has_no_link(self):
        owner = make_user("self@example.com")
        own = make_application(owner, institution=self.school)
        client = APIClient()
        client.force_authenticate(owner)
        response = client.post(f"/api/payments/link/{own.reference}/")
        self.assertEqual(response.status_code, 400)

    def test_no_link_once_the_fee_is_paid(self):
        Payment.objects.create(
            application=self.application, amount=Decimal("5000"), amount_ngn=Decimal("5000"), status="paid"
        )
        response = self.create_link()
        self.assertEqual((response.status_code, response.json()["code"]), (409, "paid"))

    @override_settings(PAYSTACK_SECRET_KEY="")
    def test_no_link_without_paystack(self):
        self.assertEqual(self.create_link().status_code, 503)

    # ── The student's page ────────────────────────────────────────────

    def code(self):
        self.create_link()
        return PaymentLink.objects.get(application=self.application).code

    def test_the_page_shows_what_a_payer_needs_and_nothing_private(self):
        response = self.public.get(f"/api/payments/pay/{self.code()}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "due")
        self.assertEqual(body["student"], "Kwame")
        self.assertEqual(body["institution"], "Maple College")
        self.assertEqual(Decimal(body["amount"]), Decimal("5000.00"))
        text = response.content.decode()
        for private in ("kwame@example.com", "+233200000000", "Mensah", "agent@example.com"):
            self.assertNotIn(private, text)

    def test_an_unknown_code_is_not_found(self):
        self.assertEqual(self.public.get("/api/payments/pay/not-a-real-code/").status_code, 404)
        self.assertEqual(self.public.post("/api/payments/pay/not-a-real-code/").status_code, 404)

    def start(self, code):
        with mock.patch("apps.payments.links.gateway.initiate", return_value=AUTH_URL) as initiate:
            response = self.public.post(f"/api/payments/pay/{code}/")
        return response, initiate

    def test_pressing_pay_opens_paystack_and_sends_the_receipt_to_the_agent(self):
        code = self.code()
        response, initiate = self.start(code)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["authorization_url"], AUTH_URL)
        kwargs = initiate.call_args.kwargs
        self.assertEqual(kwargs["email"], "agent@example.com")
        self.assertEqual(kwargs["callback_url"], f"https://apply.example.com/pay/{code}")
        self.assertEqual(Payment.objects.get(application=self.application).status, Payment.Status.PENDING)

    def test_paystack_unavailable_says_so(self):
        code = self.code()
        with mock.patch("apps.payments.links.gateway.initiate", return_value=None):
            response = self.public.post(f"/api/payments/pay/{code}/")
        self.assertEqual(response.status_code, 503)

    # ── Paystack confirms: paid, and the agent's commission at once ───

    def commission(self):
        return Commission.objects.filter(application=self.application, kind=Commission.Kind.REGISTRATION).first()

    def test_the_webhook_marks_it_paid_and_credits_the_agent(self):
        self.start(self.code())
        payment = Payment.objects.get(application=self.application)
        payment.gateway_reference = f"{payment.reference}-A1"
        payment.save(update_fields=["gateway_reference"])
        body = json.dumps({
            "event": "charge.success",
            "data": {
                "reference": payment.gateway_reference, "status": "success",
                "currency": "NGN", "amount": minor_units(payment.total_ngn),
            },
        }).encode()
        signature = hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()
        with mock.patch("apps.payments.settlement.services.notify"):
            self.public.post(
                "/api/payments/webhook/paystack/", body, content_type="application/json",
                HTTP_X_PAYSTACK_SIGNATURE=signature,
            )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertIsNotNone(self.commission())
        self.assertGreater(Wallet.objects.get(agent=self.agent).available_balance, 0)
        # The agent's Students table shows it as paid.
        listing = self.agent_client.get("/api/partners/students/").json()
        row = next(item for item in listing if item["reference"] == self.application.reference)
        self.assertEqual(row["fee_status"], "paid")

    def test_returning_from_paystack_settles_it_without_waiting_for_the_webhook(self):
        code = self.code()
        self.start(code)
        payment = Payment.objects.get(application=self.application)
        payment.gateway_reference = f"{payment.reference}-A1"
        payment.save(update_fields=["gateway_reference"])
        paid = {"status": "success", "currency": "NGN", "amount": minor_units(payment.total_ngn)}
        with mock.patch("apps.payments.links.gateway.verify", return_value=paid):
            response = self.public.get(f"/api/payments/pay/{code}/", {"reference": payment.gateway_reference})
        self.assertEqual(response.json()["status"], "paid")
        self.assertTrue(response.json()["settled_now"])
        self.assertIsNotNone(self.commission())

    def test_a_short_payment_is_not_settled(self):
        code = self.code()
        self.start(code)
        payment = Payment.objects.get(application=self.application)
        payment.gateway_reference = f"{payment.reference}-A1"
        payment.save(update_fields=["gateway_reference"])
        short = {"status": "success", "currency": "NGN", "amount": 100}
        with mock.patch("apps.payments.links.gateway.verify", return_value=short):
            response = self.public.get(f"/api/payments/pay/{code}/", {"reference": payment.gateway_reference})
        self.assertEqual(response.json()["status"], "due")
        self.assertIsNone(self.commission())

    def test_a_made_up_reference_never_reaches_paystack(self):
        code = self.code()
        self.start(code)
        with mock.patch("apps.payments.links.gateway.verify") as verify:
            self.public.get(f"/api/payments/pay/{code}/", {"reference": "GBS-FAKE-A1"})
        verify.assert_not_called()

    # ── Nothing is charged twice ──────────────────────────────────────

    def test_a_paid_fee_cannot_be_paid_again_from_the_link(self):
        code = self.code()
        Payment.objects.create(
            application=self.application, amount=Decimal("5000"), amount_ngn=Decimal("5000"), status="paid"
        )
        response, initiate = self.start(code)
        self.assertEqual(response.status_code, 409)
        initiate.assert_not_called()
        self.assertEqual(self.public.get(f"/api/payments/pay/{code}/").json()["status"], "paid")

    def test_a_transfer_waiting_for_the_desk_blocks_a_card_payment(self):
        code = self.code()
        Payment.objects.create(
            application=self.application, amount=Decimal("5000"), amount_ngn=Decimal("5000"), status="review"
        )
        response, initiate = self.start(code)
        self.assertEqual((response.status_code, response.json()["code"]), (409, "review"))
        initiate.assert_not_called()


@override_settings(PAYSTACK_SECRET_KEY=KEY, FRONTEND_URL="https://apply.example.com")
class PaymentLinkLocalCurrencyTests(TestCase):
    """The student sees the fee in their own country's currency."""

    def setUp(self):
        cache.clear()
        from apps.catalog.models import OriginCountry

        canada = DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        school = Institution.objects.create(
            slug="maple", name="Maple College", country=canada,
            application_fee=Decimal("5000"), application_fee_currency="NGN",
        )
        agent_user = make_user("agent@example.com", role=User.Role.AGENT)
        agent = AgentProfile.objects.create(user=agent_user)
        # Ghana is seeded by a migration; its rate is set here so the sum is plain.
        OriginCountry.objects.filter(currency__iexact="GHS").update(ngn_per_unit=Decimal("100"))
        self.ghana, _ = OriginCountry.objects.update_or_create(
            name="Ghana", defaults={"currency": "GHS", "symbol": "GH₵", "ngn_per_unit": Decimal("100")}
        )
        self.application = make_application(
            make_user("ama@example.com", full_name="Ama Owusu"), institution=school, submitted_by_agent=agent
        )
        client = APIClient()
        client.force_authenticate(agent_user)
        client.post(f"/api/payments/link/{self.application.reference}/")
        self.code = PaymentLink.objects.get(application=self.application).code

    def page(self):
        # No live rate in tests: the admin's Exchange rates table is used.
        with mock.patch("apps.catalog.fx.get_rates", return_value={}):
            return APIClient().get(f"/api/payments/pay/{self.code}/").json()

    def test_a_ghanaian_student_sees_cedis(self):
        self.application.origin_country = self.ghana
        self.application.save(update_fields=["origin_country"])
        body = self.page()
        self.assertEqual(body["local_currency"], "GHS")
        # The Naira charge at ₦100 per cedi.
        self.assertEqual(Decimal(body["local_amount"]), (Decimal(body["amount_ngn"]) / 100).quantize(Decimal("0.01")))
        self.assertIn("GH₵", body["local_display"])

    def test_a_nigerian_student_sees_naira_only(self):
        body = self.page()
        self.assertNotIn("local_currency", body)

    def test_no_rate_on_file_still_shows_the_page(self):
        from apps.catalog.models import OriginCountry

        OriginCountry.objects.filter(currency__iexact="GMD").update(ngn_per_unit=Decimal("0"))
        gambia, _ = OriginCountry.objects.update_or_create(
            name="Gambia", defaults={"currency": "GMD", "symbol": "D", "ngn_per_unit": Decimal("0")}
        )
        self.application.origin_country = gambia
        self.application.save(update_fields=["origin_country"])
        body = self.page()
        self.assertEqual(body["status"], "due")
        self.assertNotIn("local_currency", body)


class StudentCurrencyTests(TestCase):
    """Fee screens show the student's own country's currency only."""

    def test_currency_and_amounts_follow_the_students_country(self):
        from apps.catalog.models import OriginCountry
        from apps.payments.display import for_application, format_amount

        OriginCountry.objects.filter(currency__iexact="GHS").update(ngn_per_unit=Decimal("100"))
        ghana, _ = OriginCountry.objects.update_or_create(
            name="Ghana", defaults={"currency": "GHS", "symbol": "GH₵", "ngn_per_unit": Decimal("100")}
        )
        student = make_application(make_user("kofi@example.com"))
        nigerian = make_application(make_user("ada@example.com"))
        student.origin_country = ghana
        student.save(update_fields=["origin_country"])

        with mock.patch("apps.catalog.fx.get_rates", return_value={}):
            cedis = for_application(student)
        self.assertEqual((cedis["code"], cedis["symbol"]), ("GHS", "GH₵"))
        self.assertEqual(format_amount(Decimal("50000"), cedis), "GH₵500")
        naira = for_application(nigerian)
        self.assertEqual(naira["code"], "NGN")
        self.assertEqual(format_amount(Decimal("50000"), naira), "₦50,000")
        self.assertEqual(format_amount(Decimal("50000"), {"code": "GMD", "symbol": "D", "ngn_per_unit": "25"}), "D 2,000")
