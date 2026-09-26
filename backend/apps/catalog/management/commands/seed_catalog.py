"""Load the partner catalogue.

Safe to run repeatedly. A school or course already on file is updated in place
rather than duplicated, so re-running after an edit in the admin only corrects
what the seed actually owns.

`--prune` additionally removes schools and courses that are not in the seed. It
is how the catalogue is brought back to exactly what the admissions desk
supplied, and it refuses to delete anything an applicant has applied to, because
that would take their application with it.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.catalogue_data import COUNTRIES, SCHOOLS, course_fields
from apps.catalog.models import DestinationCountry, Institution, Program


class Command(BaseCommand):
    help = "Create or update the partner catalogue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Also remove schools and courses that are not part of the seed.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        counts = {"countries": 0, "schools": 0, "courses": 0, "updated": 0}

        for order, row in enumerate(COUNTRIES):
            country, created = DestinationCountry.objects.update_or_create(
                name=row["name"],
                defaults={
                    "code": row["code"],
                    "currency": row["currency"],
                    "currency_symbol": row["symbol"],
                    "is_european": row["european"],
                    "display_order": row.get("order", order),
                    "is_active": True,
                },
            )
            counts["countries"] += 1 if created else 0

        seeded_slugs = []
        for order, school in enumerate(SCHOOLS):
            country = DestinationCountry.objects.get(name=school["country"])
            institution, created = Institution.objects.update_or_create(
                slug=school["slug"],
                defaults={
                    "name": school["name"],
                    "country": country,
                    "location": school["location"],
                    "tagline": school["tagline"],
                    "badge": school["badge"],
                    # What the school quotes tuition and its deposit in.
                    "currency": school["currency"],
                    # What its application fee is quoted in, which is usually
                    # Naira even for a school that teaches in euros.
                    "application_fee_currency": school["fee_currency"],
                    "application_fee": Decimal(str(school["fee"])),
                    "tuition_deposit_percent": Decimal(str(school.get("deposit_percent", 0))),
                    "tuition_deposit_amount": Decimal(str(school.get("deposit_amount", 0))),
                    "tuition_summary": school["tuition_summary"],
                    "display_order": order,
                    "is_active": True,
                },
            )
            seeded_slugs.append(institution.slug)
            counts["schools"] += 1 if created else 0

            seeded_names = []
            for position, row in enumerate(school["courses"]):
                fields = course_fields(row)
                tuition = fields.pop("tuition")
                name = fields.pop("name")
                _, made = Program.objects.update_or_create(
                    institution=institution,
                    name=name,
                    defaults={
                        **fields,
                        "tuition": None if tuition is None else Decimal(str(tuition)),
                        "display_order": position,
                    },
                )
                seeded_names.append(name)
                counts["courses"] += 1 if made else 0
                counts["updated"] += 0 if made else 1

            if options["prune"]:
                stale = institution.programs.exclude(name__in=seeded_names)
                blocked, removed = self._drop_courses(stale)
                if removed:
                    self.stdout.write(
                        f"  {institution.name}: removed {removed} course(s) not in the seed"
                    )
                for course in blocked:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {institution.name}: kept {course} because an application uses it"
                        )
                    )

        if options["prune"]:
            self._prune_schools(seeded_slugs)

        self.stdout.write(
            self.style.SUCCESS(
                "Catalogue loaded. "
                f"{DestinationCountry.objects.count()} countries, "
                f"{Institution.objects.count()} schools, "
                f"{Program.objects.count()} courses "
                f"({counts['courses']} new, {counts['updated']} updated)."
            )
        )

    def _drop_courses(self, queryset):
        """Remove courses nobody has applied to. Returns (kept, removed)."""
        kept, removed = [], 0
        for course in queryset:
            if course.applications.exists():
                kept.append(course.name)
                continue
            course.delete()
            removed += 1
        return kept, removed

    def _prune_schools(self, keep_slugs):
        for institution in Institution.objects.exclude(slug__in=keep_slugs):
            if institution.applications.exists():
                # Deleting it would take live applications with it, so it is
                # hidden instead: gone from the site, intact in the records.
                institution.is_active = False
                institution.save(update_fields=["is_active"])
                self.stdout.write(
                    self.style.WARNING(
                        f"  {institution.name} has applications, so it was hidden "
                        "rather than deleted."
                    )
                )
                continue
            name = institution.name
            institution.delete()
            self.stdout.write(f"  removed {name}, which is not in the seed")

        for country in DestinationCountry.objects.exclude(
            name__in=[c["name"] for c in COUNTRIES]
        ):
            if country.institutions.exists():
                country.is_active = False
                country.save(update_fields=["is_active"])
                self.stdout.write(
                    self.style.WARNING(f"  {country.name} still has schools, so it was hidden.")
                )
                continue
            name = country.name
            country.delete()
            self.stdout.write(f"  removed {name}, which is not in the seed")
