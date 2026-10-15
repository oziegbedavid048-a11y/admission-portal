"""A change saved in the admin shows on the site on the very next request."""

from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import DestinationCountry, Institution


class CatalogueFreshnessTests(TestCase):
    def setUp(self):
        france = DestinationCountry.objects.create(name="France", code="FR", currency="EUR")
        self.school = Institution.objects.create(
            slug="paris", name="Paris School", country=france, currency="EUR",
            application_fee=Decimal("135"), tuition_deposit_amount=Decimal("1000"),
        )

    def deposit(self):
        response = self.client.get("/api/catalog/institutions/", {"country": "France"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        rows = response.json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        return rows[0]["tuition_deposit_amount"], rows[0]["tuition_deposit_percent"]

    def test_a_deposit_changed_in_the_admin_shows_at_once(self):
        self.assertEqual(self.deposit(), ("1000.00", "0.00"))
        # Cached now. Staff change the deposit in the admin.
        self.school.tuition_deposit_amount = Decimal("0")
        self.school.tuition_deposit_percent = Decimal("40")
        self.school.save()
        self.assertEqual(self.deposit(), ("0.00", "40.00"))

    def test_the_fee_is_sent_with_the_school_s_currency_signs(self):
        response = self.client.get("/api/catalog/institutions/", {"country": "France"})
        rows = response.json()
        row = (rows["results"] if isinstance(rows, dict) else rows)[0]
        self.assertEqual((row["application_fee"], row["application_fee_currency"]), ("135.00", "EUR"))
        self.assertEqual((row["fee_symbol"], row["tuition_symbol"]), ("€", "€"))
