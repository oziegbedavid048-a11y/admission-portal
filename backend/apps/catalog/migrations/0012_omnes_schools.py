"""Add five French schools and their courses to the live catalogue.

ECE Engineering School, ESCE, INSEEC, HEIP and Sup de Pub, from
apps/catalog/catalogue_omnes.py. Deploys run migrations but not the seed, so
this is what puts them on the site.

Adding only. A school already on file (same slug) is left exactly as it is,
in case the desk has edited it in the admin, and so is any course it already
has; only what is missing is created. Nothing is changed or deleted, and
undoing this migration removes nothing.
"""

from decimal import Decimal

from django.db import migrations
from django.db.models import F, Max


def add_schools(apps, schema_editor):
    from apps.catalog.catalogue_omnes import OMNES_SCHOOLS

    DestinationCountry = apps.get_model("catalog", "DestinationCountry")
    Institution = apps.get_model("catalog", "Institution")
    Program = apps.get_model("catalog", "Program")
    CatalogVersion = apps.get_model("catalog", "CatalogVersion")

    country = DestinationCountry.objects.filter(name="France").first()
    if country is None:
        country = DestinationCountry.objects.create(
            name="France", code="FR", currency="EUR", currency_symbol="€", is_european=True, is_active=True
        )
    next_order = (Institution.objects.aggregate(top=Max("display_order"))["top"] or 0) + 1

    for school in OMNES_SCHOOLS:
        institution = Institution.objects.filter(slug=school["slug"]).first()
        if institution is None:
            institution = Institution.objects.create(
                slug=school["slug"],
                name=school["name"],
                country=country,
                location=school["location"],
                tagline=school["tagline"],
                badge=school["badge"],
                currency=school["currency"],
                application_fee_currency=school["fee_currency"],
                application_fee=Decimal(str(school["fee"])),
                tuition_deposit_amount=Decimal(str(school.get("deposit_amount", 0))),
                tuition_deposit_percent=Decimal(str(school.get("deposit_percent", 0))),
                tuition_summary=school["tuition_summary"],
                display_order=next_order,
                is_active=True,
            )
            next_order += 1

        existing = set(institution.programs.values_list("name", flat=True))
        for position, row in enumerate(school["courses"]):
            name, level, duration, tuition = row[0], row[1], row[2], row[3]
            if name in existing:
                continue
            Program.objects.create(
                institution=institution,
                name=name,
                level=level,
                duration=duration,
                tuition=None if tuition is None else Decimal(str(tuition)),
                intake=row[4] if len(row) > 4 else "",
                note=row[5] if len(row) > 5 else "",
                qualification_level=row[6] if len(row) > 6 else "",
                scholarship=row[7] if len(row) > 7 else "",
                display_order=position,
            )

    # The catalogue's cached answers are keyed on this, so the new schools
    # show at once (the admin's save signals do not run in a migration).
    if not CatalogVersion.objects.filter(pk=1).update(value=F("value") + 1):
        CatalogVersion.objects.get_or_create(pk=1, defaults={"value": 2})


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0011_catalog_version"),
    ]

    operations = [
        migrations.RunPython(add_schools, migrations.RunPython.noop),
    ]
