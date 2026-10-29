"""A change saved in the admin shows on the site on the very next request."""

from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import DestinationCountry, Institution


class CatalogueFreshnessTests(TestCase):
    def setUp(self):
        france = DestinationCountry.objects.update_or_create(name="France", defaults=dict(code="FR", currency="EUR"))[0]
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


class OmnesSchoolsMigrationTests(TestCase):
    """Five French schools added by migration 0012 (catalogue_omnes.py)."""

    def test_the_five_schools_and_their_courses_are_on_file(self):
        from decimal import Decimal

        from apps.catalog.catalogue_omnes import OMNES_SCHOOLS
        from apps.catalog.models import Institution

        # The first list (26 Oct) plus the full 2026/2027 list for three (29 Oct).
        expected = {"ece-engineering-school": 11 + 18, "esce": 3 + 15, "inseec": 16 + 251, "heip": 13, "sup-de-pub": 26}
        self.assertEqual({school["slug"] for school in OMNES_SCHOOLS}, set(expected))
        for slug, count in expected.items():
            school = Institution.objects.get(slug=slug)
            self.assertEqual(school.country.name, "France")
            self.assertTrue(school.is_active)
            self.assertEqual(school.currency, "EUR")
            self.assertEqual(school.tuition_deposit_amount, Decimal("3500"))
            self.assertEqual(school.programs.count(), count, slug)

        ai = Institution.objects.get(slug="ece-engineering-school").programs.get(name="Bachelor in Artificial Intelligence")
        self.assertEqual((ai.level, ai.duration, ai.tuition), ("bachelors", "3 years", Decimal("8850.00")))
        self.assertEqual(ai.note, "Taught in French / English")

    def test_the_public_course_list_shows_them(self):
        response = self.client.get("/api/catalog/institutions/")
        self.assertEqual(response.status_code, 200)
        slugs = {row["slug"] for row in (response.json() if isinstance(response.json(), list) else response.json()["results"])}
        self.assertTrue({"ece-engineering-school", "esce", "inseec", "heip", "sup-de-pub"} <= slugs)

    def test_the_full_list_reads_as_supplied(self):
        from decimal import Decimal

        from apps.catalog.models import Institution

        inseec = Institution.objects.get(slug="inseec")
        course = inseec.programs.get(name="MSc - Marseille - M1 - Audit & Contrôle de Gestion")
        self.assertEqual((course.level, course.duration, course.tuition), ("masters", "2 years", Decimal("12990.00")))
        self.assertIn("€13,", course.note)  # the instalment price
        self.assertIn("Marseille campus", course.note)
        third_year = inseec.programs.get(name="Bachelor - Beaune - B3 - Oenotourisme")
        self.assertEqual(third_year.duration, "1 year (enters 3rd year)")
        ece = Institution.objects.get(slug="ece-engineering-school")
        self.assertTrue(ece.programs.filter(name="MSc CGE - Paris - M1 - Cybersecurity Manager - 100% English").exists())
