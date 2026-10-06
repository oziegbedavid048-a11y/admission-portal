"""Agents outside Nigeria are paid and shown in their own currency.

Commissions are set in Naira and converted at the exchange rate of the moment
they are credited; that amount never changes afterwards. Agents in Nigeria
are untouched.
"""

from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.applications import services
from apps.applications.tests.factories import make_application, make_user
from apps.catalog.models import OriginCountry
from apps.partners.models import (
    AgentProfile,
    Commission,
    Loan,
    SupervisorProfile,
    Wallet,
    Withdrawal,
)

RATES = "apps.catalog.fx.get_rates"


def live(units_per_naira):
    """A live rate table as the provider returns it (base NGN)."""
    return {"rates": {"KES": units_per_naira}, "live": True}


class AgentCurrencyTests(TestCase):
    def setUp(self):
        # Rate limits and cached exchange rates live in the cache, which other
        # tests share; each test here starts clean.
        from django.core.cache import cache

        cache.clear()
        OriginCountry.objects.get_or_create(
            name="Nigeria", defaults={"currency": "NGN", "symbol": "₦", "ngn_per_unit": Decimal("1")}
        )
        OriginCountry.objects.create(name="Kenya", currency="KES", symbol="KSh", ngn_per_unit=Decimal("12"))
        self.user = make_user("kenya.agent@example.com", role=User.Role.AGENT, country="Kenya")
        self.agent = AgentProfile.objects.create(user=self.user)
        self.wallet = Wallet.objects.create(agent=self.agent)
        self.wallet.sync_currency()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def student(self, email="s@example.com"):
        return make_application(make_user(email), submitted_by_agent=self.agent)

    def credit(self, application, kind, units_per_naira):
        with mock.patch(RATES, return_value=live(units_per_naira)):
            with self.captureOnCommitCallbacks(execute=True):
                return services.award_commission(application, kind)

    # ── The wallet's currency ──

    def test_a_kenyan_agents_wallet_is_in_shillings(self):
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).currency, "KES")

    def test_a_nigerian_agent_stays_in_naira(self):
        user = make_user("ng.agent@example.com", role=User.Role.AGENT, country="Nigeria")
        agent = AgentProfile.objects.create(user=user)
        wallet = Wallet.objects.create(agent=agent)
        wallet.sync_currency()
        application = make_application(make_user("ng.s@example.com"), submitted_by_agent=agent)
        amount = services.award_commission(application, Commission.Kind.REGISTRATION)
        self.assertEqual(amount, Decimal("30000"))
        commission = Commission.objects.get(application=application)
        self.assertEqual((commission.currency, commission.amount, commission.fx_rate), ("NGN", Decimal("30000.00"), Decimal("1")))
        self.assertEqual(Wallet.objects.get(agent=agent).total_earned, Decimal("30000.00"))

    def test_a_country_not_on_the_rate_table_falls_back_to_naira(self):
        user = make_user("x.agent@example.com", role=User.Role.AGENT, country="Atlantis")
        agent = AgentProfile.objects.create(user=user)
        wallet = Wallet.objects.create(agent=agent)
        wallet.sync_currency()
        self.assertEqual(wallet.currency, "NGN")

    def test_signing_up_creates_the_wallet_in_the_agents_currency(self):
        from apps.accounts.serializers import AgentRegistrationSerializer

        serializer = AgentRegistrationSerializer(data={
            "email": "new.kenyan@example.com", "full_name": "Wanjiku Kamau", "phone": "+254700000000",
            "country": "Kenya", "password": "Strong-pass-123", "bank_name": "KCB",
            "account_number": "0123456789", "account_name": "Wanjiku Kamau",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.agent_profile.wallet.currency, "KES")

    # ── Commissions at the rate of the moment ──

    def test_the_registration_commission_is_converted_at_the_moment_it_is_credited(self):
        application = self.student()
        amount = self.credit(application, Commission.Kind.REGISTRATION, 0.084)
        self.assertEqual(amount, Decimal("2520.00"))  # 30,000 x 0.084
        commission = Commission.objects.get(application=application, kind=Commission.Kind.REGISTRATION)
        self.assertEqual(commission.currency, "KES")
        self.assertEqual(commission.amount, Decimal("2520.00"))
        self.assertEqual(commission.amount_ngn, Decimal("30000.00"))
        self.assertEqual(commission.fx_rate, Decimal("11.904762"))
        wallet = Wallet.objects.get(pk=self.wallet.pk)
        self.assertEqual(wallet.total_earned, Decimal("2520.00"))
        self.assertEqual(wallet.registration_commission_total, Decimal("2520.00"))

    def test_a_later_rate_never_changes_money_already_credited(self):
        application = self.student()
        self.credit(application, Commission.Kind.REGISTRATION, 0.084)
        # The rate moves; the visa commission is converted at the new one.
        self.credit(application, Commission.Kind.VISA, 0.1)
        registration = Commission.objects.get(application=application, kind=Commission.Kind.REGISTRATION)
        visa = Commission.objects.get(application=application, kind=Commission.Kind.VISA)
        self.assertEqual(registration.amount, Decimal("2520.00"))
        self.assertEqual(visa.amount, Decimal("5000.00"))  # 50,000 x 0.1
        self.assertEqual(visa.amount_ngn, Decimal("50000.00"))
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).total_earned, Decimal("7520.00"))

    def test_the_reference_rate_is_used_when_the_live_rate_is_unavailable(self):
        application = self.student()
        with mock.patch(RATES, return_value={"rates": {}, "live": False}):
            amount = services.award_commission(application, Commission.Kind.REGISTRATION)
        self.assertEqual(amount, Decimal("2500.00"))  # 30,000 / 12

    def test_a_commission_is_still_paid_only_once(self):
        application = self.student()
        self.credit(application, Commission.Kind.REGISTRATION, 0.084)
        self.assertEqual(self.credit(application, Commission.Kind.REGISTRATION, 0.2), 0)
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).total_earned, Decimal("2520.00"))

    def test_the_commission_email_is_in_shillings(self):
        mail.outbox.clear()
        with mock.patch("apps.accounts.emails._send") as send:
            self.credit(self.student(), Commission.Kind.REGISTRATION, 0.084)
        kwargs = send.call_args.kwargs
        self.assertIn("KSh 2,520", kwargs["subject"])
        self.assertNotIn("₦", kwargs["subject"] + " ".join(kwargs["paragraphs"]))

    # ── Once money lands, the currency is fixed ──

    def test_changing_country_before_any_money_moves_the_currency(self):
        OriginCountry.objects.create(name="Ghana", currency="GHS", symbol="GH₵", ngn_per_unit=Decimal("100"))
        response = self.client.patch("/api/partners/me/", {"country": "Ghana"}, format="json")
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).currency, "GHS")

    def test_a_country_typed_loosely_is_saved_as_the_table_spells_it(self):
        OriginCountry.objects.create(name="Ghana", currency="GHS", symbol="GH₵", ngn_per_unit=Decimal("100"))
        response = self.client.patch("/api/partners/me/", {"country": "  gHaNa "}, format="json")
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.user.refresh_from_db()
        self.assertEqual(self.user.country, "Ghana")
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).currency, "GHS")

    def test_changing_country_after_money_landed_keeps_the_currency(self):
        self.credit(self.student(), Commission.Kind.REGISTRATION, 0.084)
        OriginCountry.objects.create(name="Ghana", currency="GHS", symbol="GH₵", ngn_per_unit=Decimal("100"))
        self.client.patch("/api/partners/me/", {"country": "Ghana"}, format="json")
        self.assertEqual(Wallet.objects.get(pk=self.wallet.pk).currency, "KES")

    # ── What the dashboard reads ──

    def test_the_wallet_api_speaks_shillings_and_converts_the_limits(self):
        with mock.patch(RATES, return_value={"rates": {}, "live": False}):
            data = self.client.get("/api/partners/wallet/").json()
        self.assertEqual(data["currency"], "KES")
        self.assertEqual(data["symbol"], "KSh")
        self.assertEqual(Decimal(str(data["minimum_withdrawal"])), Decimal("8334"))  # 100,000 / 12, rounded up
        self.assertEqual(Decimal(str(data["loan_min"])), Decimal("834"))  # 10,000 / 12
        self.assertEqual(Decimal(str(data["loan_max"])), Decimal("6667"))  # 80,000 / 12

    def test_earning_history_rows_carry_the_currency(self):
        self.credit(self.student(), Commission.Kind.REGISTRATION, 0.084)
        rows = self.client.get("/api/partners/wallet/history/").json()
        self.assertEqual(rows[0]["currency"], "KES")
        self.assertEqual(rows[0]["amount"], "2520.00")

    def test_withdrawals_use_the_converted_minimum(self):
        Wallet.objects.filter(pk=self.wallet.pk).update(total_earned=Decimal("10000"))
        self.wallet.refresh_from_db()  # the test client reuses this agent's cached wallet
        with mock.patch(RATES, return_value={"rates": {}, "live": False}):
            too_small = self.client.post("/api/partners/withdrawals/", {"amount": "8000"}, format="json")
            enough = self.client.post("/api/partners/withdrawals/", {"amount": "8334"}, format="json")
        self.assertEqual(too_small.status_code, 400)
        self.assertIn("KSh 8,334", str(too_small.json()))
        self.assertIn(enough.status_code, (200, 201), enough.content[:300])
        self.assertEqual(Withdrawal.objects.get().currency, "KES")

    def test_ads_funding_is_requested_in_shillings(self):
        with mock.patch(RATES, return_value={"rates": {}, "live": False}):
            too_much = self.client.post("/api/partners/loans/", {"requested_amount": "80000", "purpose": "Facebook"}, format="json")
            fine = self.client.post("/api/partners/loans/", {"requested_amount": "5000", "purpose": "Facebook"}, format="json")
        self.assertEqual(too_much.status_code, 400)
        self.assertIn("KSh", str(too_much.json()))
        self.assertEqual(fine.status_code, 201, fine.content[:300])
        self.assertEqual(Loan.objects.get().currency, "KES")

    # ── The sales manager still counts in Naira ──

    def test_the_sales_manager_team_total_is_in_naira(self):
        manager_user = make_user("manager@example.com", role=User.Role.SUPERVISOR)
        manager = SupervisorProfile.objects.create(user=manager_user)
        AgentProfile.objects.filter(pk=self.agent.pk).update(supervisor=manager)
        self.credit(self.student(), Commission.Kind.REGISTRATION, 0.084)
        client = APIClient()
        client.force_authenticate(manager_user)
        data = client.get("/api/supervisors/overview/").json()
        self.assertEqual(Decimal(str(data["earnings"]["team_earned"])), Decimal("30000.00"))


class AfricanCountriesTests(TestCase):
    """Every African country an agent can sign up from has its own currency."""

    def test_no_african_country_falls_back_to_naira(self):
        import importlib
        import re
        from pathlib import Path

        from apps.partners.currency import currency_for_country, naira_per_unit

        migration = importlib.import_module("apps.catalog.migrations.0008_african_currencies")
        for name, currency, _, _ in migration.AFRICA:
            got, _ = currency_for_country(name)
            self.assertEqual(got, currency, name)
            with mock.patch(RATES, return_value={"rates": {}, "live": False}):
                self.assertGreater(naira_per_unit(got), 0, name)  # a reference rate exists

        # And the names on the sign-up list are the names on the table.
        countries_js = Path(__file__).resolve().parents[4] / "frontend" / "src" / "lib" / "countries.js"
        if countries_js.exists():
            listed = set(re.findall(r"'([^']+)'", countries_js.read_text(encoding="utf-8")))
            for name, *_ in migration.AFRICA:
                self.assertIn(name, listed, f"{name} is not on the agent sign-up list")
