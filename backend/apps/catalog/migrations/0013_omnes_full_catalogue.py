"""Add the full 2026/2027 ECE, ESCE and INSEEC course list (284 courses).

From apps/catalog/catalogue_omnes_full.py, under the schools added by 0012
(all in France). Adding only: a course already on file at that school (same
name) is left untouched and nothing is deleted. Each school's tuition range is
recalculated from its courses, INSEEC's location lists its campuses, and the
catalogue cache version is bumped so the courses show at once.
"""

from decimal import Decimal

from django.db import migrations
from django.db.models import F, Max

# INSEEC teaches on several campuses; each course names its own.
INSEEC_LOCATION = "Paris, Bordeaux, Lyon, Marseille and other campuses, France"


def add_courses(apps, schema_editor):
    from apps.catalog.catalogue_omnes import OMNES_SCHOOLS
    from apps.catalog.catalogue_omnes_full import BY_SLUG

    DestinationCountry = apps.get_model("catalog", "DestinationCountry")
    Institution = apps.get_model("catalog", "Institution")
    Program = apps.get_model("catalog", "Program")
    CatalogVersion = apps.get_model("catalog", "CatalogVersion")

    schools = {school["slug"]: school for school in OMNES_SCHOOLS}
    for slug, courses in BY_SLUG.items():
        institution = Institution.objects.filter(slug=slug).first()
        if institution is None:
            # 0012 creates these; this only covers a database where one was removed.
            school = schools[slug]
            country, _ = DestinationCountry.objects.get_or_create(
                name="France", defaults={"code": "FR", "currency": "EUR", "currency_symbol": "€", "is_european": True}
            )
            institution = Institution.objects.create(
                slug=slug, name=school["name"], country=country, location=school["location"],
                tagline=school["tagline"], badge=school["badge"], currency="EUR",
                application_fee_currency=school["fee_currency"], application_fee=Decimal(str(school["fee"])),
                tuition_deposit_amount=Decimal(str(school.get("deposit_amount", 0))),
                tuition_summary=school["tuition_summary"], is_active=True,
            )
        existing = set(institution.programs.values_list("name", flat=True))
        order = (institution.programs.aggregate(top=Max("display_order"))["top"] or 0) + 1
        for name, level, duration, tuition, intake, note, qualification in courses:
            if name in existing:
                continue
            Program.objects.create(
                institution=institution,
                name=name,
                level=level,
                duration=duration,
                tuition=None if tuition is None else Decimal(str(tuition)),
                intake=intake,
                note=note,
                qualification_level=qualification,
                display_order=order,
            )
            existing.add(name)
            order += 1

        # The tuition range shown for the school, now that it has more courses.
        prices = [price for price in institution.programs.exclude(tuition=None).values_list("tuition", flat=True)]
        if prices:
            institution.tuition_summary = f"€{min(prices):,.0f} - €{max(prices):,.0f} / year"
        if slug == "inseec":
            institution.location = INSEEC_LOCATION
        institution.save(update_fields=["tuition_summary", "location"])

    if not CatalogVersion.objects.filter(pk=1).update(value=F("value") + 1):
        CatalogVersion.objects.get_or_create(pk=1, defaults={"value": 2})


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_omnes_schools"),
    ]

    operations = [
        migrations.RunPython(add_courses, migrations.RunPython.noop),
    ]
