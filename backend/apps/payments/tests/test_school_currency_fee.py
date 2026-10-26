"""The application fee is shown in the school's currency and charged in Naira."""

import importlib
from decimal import Decimal
from unittest import mock

from django.apps import apps as registry
from django.test import TestCase

from apps.applications.tests.factories import make_application, make_user
from apps.catalog.models import DestinationCountry, Institution, OriginCountry
from apps.payments.views import quote_for, transfer_amount_ngn

LIVE_EUR = Decimal("1650")


class SchoolCurrencyFeeTests(TestCase):
    def setUp(self):
        self.france = DestinationCountry.objects.update_or_create(name="France", defaults=dict(code="FR", currency="EUR", currency_symbol="€"))[0]
        OriginCountry.objects.get_or_create(
            name="France", defaults={"currency": "EUR", "symbol": "€", "ngn_per_unit": Decimal("1680")}
        )
        self.school = Institution.objects.create(
            slug="paris", name="Paris School", country=self.france, currency="EUR", application_fee=Decimal("135")
        )
        self.applicant = make_user("ghana@example.com")
        self.application = make_application(self.applicant, institution=self.school)

    def quote(self):
        with mock.patch("apps.partners.currency.naira_per_unit", return_value=LIVE_EUR):
            return quote_for(self.application)

    def test_a_new_school_quotes_its_fee_in_its_own_currency(self):
        self.assertEqual(self.school.application_fee_currency, "EUR")

    def test_the_fee_is_shown_in_euros_whatever_the_applicant_s_country(self):
        quote = self.quote()
        self.assertEqual(quote["currency"], "EUR")
        self.assertEqual(quote["symbol"], "€")
        self.assertEqual(quote["amount"], Decimal("135.00"))

    def test_the_card_is_charged_the_naira_equivalent_at_the_live_rate(self):
        quote = self.quote()
        self.assertEqual(quote["amount_ngn"], Decimal("222750.00"))
        self.assertEqual(quote["total_ngn"], quote["amount_ngn"] + quote["processing_fee_ngn"])
        # Paystack's cut is stated in euros at the same rate.
        self.assertEqual(quote["processing_fee"], (quote["processing_fee_ngn"] / LIVE_EUR).quantize(Decimal("0.01")))

    def test_a_bank_transfer_is_the_naira_fee_rounded_up_to_the_next_hundred(self):
        self.assertEqual(transfer_amount_ngn(Decimal("198000.00")), Decimal("198000.00"))
        self.assertEqual(transfer_amount_ngn(Decimal("198000.01")), Decimal("198100.00"))
        self.assertEqual(transfer_amount_ngn(Decimal("212347.60")), Decimal("212400.00"))
        self.assertEqual(self.quote()["transfer_amount_ngn"], Decimal("222800.00"))

    def test_never_charged_below_two_hundred_thousand_naira(self):
        # The euro weakens: 135 euros would now be only 175,500 Naira.
        with mock.patch("apps.partners.currency.naira_per_unit", return_value=Decimal("1300")):
            quote = quote_for(self.application)
        self.assertEqual(quote["amount"], Decimal("135.00"))
        self.assertEqual(quote["amount_ngn"], Decimal("200000.00"))
        self.assertEqual(quote["transfer_amount_ngn"], Decimal("200000.00"))

    def test_the_minimum_can_be_lowered_per_school(self):
        self.school.minimum_fee_ngn = Decimal("0")
        self.school.save()
        with mock.patch("apps.partners.currency.naira_per_unit", return_value=Decimal("1300")):
            self.assertEqual(quote_for(self.application)["amount_ngn"], Decimal("175500.00"))

    def test_a_fee_free_school_is_waived(self):
        self.school.application_fee = Decimal("0")
        self.school.save()
        self.assertTrue(self.quote()["waived"])


class FeeConversionMigrationTests(TestCase):
    def test_naira_fees_are_requoted_in_the_school_currency_once(self):
        canada = DestinationCountry.objects.create(name="Canada", code="CA", currency="CAD")
        OriginCountry.objects.get_or_create(
            name="Canada", defaults={"currency": "CAD", "symbol": "C$", "ngn_per_unit": Decimal("1120")}
        )
        france = DestinationCountry.objects.update_or_create(name="France", defaults=dict(code="FR", currency="EUR"))[0]
        OriginCountry.objects.get_or_create(
            name="France", defaults={"currency": "EUR", "symbol": "€", "ngn_per_unit": Decimal("1680")}
        )
        naira_ca = Institution.objects.create(
            slug="ca", name="CA", country=canada, currency="CAD",
            application_fee_currency="NGN", application_fee=Decimal("200000"),
        )
        naira_fr = Institution.objects.create(
            slug="fr", name="FR", country=france, currency="EUR",
            application_fee_currency="NGN", application_fee=Decimal("200000"),
        )
        ucam = Institution.objects.create(
            slug="ucam", name="UCAM", country=france, currency="EUR",
            application_fee_currency="EUR", application_fee=Decimal("150"),
        )
        migration = importlib.import_module("apps.catalog.migrations.0009_fee_in_school_currency")
        migration.fees_into_school_currency(registry, None)

        naira_ca.refresh_from_db()
        naira_fr.refresh_from_db()
        ucam.refresh_from_db()
        self.assertEqual((naira_ca.application_fee_currency, naira_ca.application_fee), ("CAD", Decimal("179.00")))
        self.assertEqual((naira_fr.application_fee_currency, naira_fr.application_fee), ("EUR", Decimal("120.00")))
        self.assertEqual((ucam.application_fee_currency, ucam.application_fee), ("EUR", Decimal("150.00")))
