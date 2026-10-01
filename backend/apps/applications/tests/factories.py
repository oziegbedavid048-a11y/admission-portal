"""Small helpers that build the records a security test needs."""

from decimal import Decimal

from apps.accounts.models import User
from apps.applications.models import Application
from apps.catalog.models import DestinationCountry, OriginCountry


def make_user(email, role=User.Role.APPLICANT, **extra):
    return User.objects.create_user(
        email=email,
        password="Strong-pass-123",
        full_name=extra.pop("full_name", "Test Person"),
        role=role,
        **extra,
    )


def make_application(applicant, **extra):
    origin, _ = OriginCountry.objects.get_or_create(
        name="Nigeria",
        defaults={"currency": "NGN", "symbol": "N", "ngn_per_unit": Decimal("1")},
    )
    destination, _ = DestinationCountry.objects.get_or_create(
        name="Canada", defaults={"code": "CA", "currency": "CAD"}
    )
    return Application.objects.create(
        applicant=applicant,
        full_name=extra.pop("full_name", applicant.full_name),
        email=extra.pop("email", applicant.email),
        origin_country=origin,
        destination_country=destination,
        **extra,
    )
