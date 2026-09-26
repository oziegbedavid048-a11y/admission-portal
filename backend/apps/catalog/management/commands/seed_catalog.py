"""Load the reference catalogue: origin countries, destinations, schools, FAQs.

The data lives in ``apps/catalog/data/catalog.json``, which was lifted from the
original prototype's ``js/data.js``. The command is idempotent, so running it
again after editing the JSON updates rows in place rather than duplicating them.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import (
    DestinationCountry,
    FaqItem,
    Institution,
    OriginCountry,
    Program,
)

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "catalog.json"

# Same buckets the prototype used, in the order they are shown.
LEVEL_PATTERNS = [
    (
        Program.Level.PHD,
        re.compile(r"\bphd\b|ph\.d|doctoral|doctor\s+of", re.I),
    ),
    (
        Program.Level.MASTERS,
        re.compile(r"master|mast[eè]re?|mba|msc\b|m\.sc|\bma\b|mphil|postgrad(uate)?", re.I),
    ),
    (
        Program.Level.BACHELORS,
        re.compile(
            r"bachelor|bba|\bba\s*\(|\bbsc\b|\bb\.sc|beng|b\.eng|bcomm|b\.comm|\bba\s+in|^degree\s+in",
            re.I,
        ),
    ),
    (
        Program.Level.DIPLOMAS,
        re.compile(r"diploma|certificate|othm|ncc\s*level", re.I),
    ),
]


def classify(name):
    for level, pattern in LEVEL_PATTERNS:
        if pattern.search(name):
            return level
    return Program.Level.OTHER


class Command(BaseCommand):
    help = "Seed origin countries, destinations, partner institutions and FAQs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing institutions and programs before loading.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not DATA_FILE.exists():
            self.stderr.write(f"Catalogue file not found: {DATA_FILE}")
            return

        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))

        if options["flush"]:
            Program.objects.all().delete()
            Institution.objects.all().delete()

        origins = self._load_origins(payload["ORIGIN_COUNTRIES"])
        destinations = self._load_destinations(payload["DESTINATION_COUNTRIES"])
        schools, programs = self._load_institutions(
            payload["INSTITUTIONS_BY_COUNTRY"], destinations
        )
        faqs = self._load_faqs(payload["FAQ_ITEMS"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue loaded: {origins} origin countries, {destinations and len(destinations)} "
                f"destinations, {schools} institutions, {programs} programmes, {faqs} FAQs."
            )
        )

    def _load_origins(self, rows):
        for row in rows:
            OriginCountry.objects.update_or_create(
                name=row["name"],
                defaults={
                    "currency": row["currency"],
                    "symbol": row["symbol"],
                    "ngn_per_unit": Decimal(str(row["ngnPerUnit"])),
                },
            )
        return len(rows)

    def _load_destinations(self, rows):
        mapping = {}
        for order, row in enumerate(rows):
            country, _ = DestinationCountry.objects.update_or_create(
                name=row["name"],
                defaults={
                    "code": row["code"],
                    "currency": row["currency"],
                    "currency_symbol": row.get("currencySymbol", ""),
                    "is_european": bool(row.get("isEuropean")),
                    "display_order": order,
                    "is_active": True,
                },
            )
            mapping[row["name"]] = country
        return mapping

    def _load_institutions(self, by_country, destinations):
        school_count = 0
        program_count = 0

        for country_name, schools in by_country.items():
            country = destinations.get(country_name)
            if country is None:
                country, _ = DestinationCountry.objects.get_or_create(
                    name=country_name,
                    defaults={"code": country_name[:2].upper(), "currency": "USD"},
                )
                destinations[country_name] = country

            for order, row in enumerate(schools):
                institution, _ = Institution.objects.update_or_create(
                    slug=slugify(row["id"]) or slugify(row["name"]),
                    defaults={
                        "name": row["name"],
                        "country": country,
                        "location": row.get("location", ""),
                        "tagline": row.get("tagline", ""),
                        "badge": row.get("badge", "Partner School"),
                        "currency": row.get("currency", country.currency),
                        "application_fee": Decimal(str(row.get("appFee", 0) or 0)),
                        "tuition_summary": row.get("tuition", ""),
                        "features": row.get("features", []),
                        "display_order": order,
                        "is_active": True,
                    },
                )
                school_count += 1
                program_count += self._load_programs(institution, row.get("programs", []))

        return school_count, program_count

    def _load_programs(self, institution, entries):
        count = 0
        seen = set()
        for order, entry in enumerate(entries):
            if isinstance(entry, str):
                name, details = entry, {}
            else:
                name, details = entry.get("name", ""), entry
            name = (name or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)

            tuition = details.get("tuition")
            Program.objects.update_or_create(
                institution=institution,
                name=name,
                defaults={
                    "level": classify(name),
                    "duration": details.get("duration", ""),
                    "qualification_level": details.get("level", ""),
                    "tuition": Decimal(str(tuition)) if tuition else None,
                    "intake": details.get("intake", ""),
                    "note": details.get("note", ""),
                    "scholarship": details.get("scholarship", ""),
                    "display_order": order,
                },
            )
            count += 1
        return count

    def _load_faqs(self, rows):
        for order, row in enumerate(rows):
            FaqItem.objects.update_or_create(
                question=row["q"],
                defaults={"answer": row["a"], "display_order": order, "is_active": True},
            )
        return len(rows)
