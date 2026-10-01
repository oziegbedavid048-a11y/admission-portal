from django.db.models import Count, Prefetch, Q
from rest_framework import viewsets
from decimal import Decimal

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.applications.constants import APPLICATION_FEE_NGN
from apps.payments.fees import processing_fee_ngn

from .models import DestinationCountry, FaqItem, Institution, OriginCountry, Program
from .fx import get_rates
from .serializers import (
    DestinationCountrySerializer,
    FaqItemSerializer,
    InstitutionSerializer,
    OriginCountrySerializer,
    ProgramCatalogSerializer,
)


class ReadOnlyPublicViewSet(viewsets.ReadOnlyModelViewSet):
    def list(self, request, *args, **kwargs):
        return cached_catalog(super().list)(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return cached_catalog(super().retrieve)(request, *args, **kwargs)

    permission_classes = (AllowAny,)
    pagination_class = None


class OriginCountryViewSet(ReadOnlyPublicViewSet):
    queryset = OriginCountry.objects.all()
    serializer_class = OriginCountrySerializer
    search_fields = ("name", "currency")


class DestinationCountryViewSet(ReadOnlyPublicViewSet):
    serializer_class = DestinationCountrySerializer

    def get_queryset(self):
        # Counted in the same query, rather than two extra queries per country.
        return DestinationCountry.objects.filter(is_active=True).annotate(
            institution_total=Count("institutions", filter=Q(institutions__is_active=True), distinct=True),
            program_total=Count("institutions__programs", filter=Q(institutions__is_active=True), distinct=True),
        )


class InstitutionViewSet(ReadOnlyPublicViewSet):
    serializer_class = InstitutionSerializer
    lookup_field = "slug"
    search_fields = ("name", "location", "tagline", "programs__name")
    filterset_fields = {"country__name": ["exact", "iexact"]}

    def get_queryset(self):
        queryset = (
            Institution.objects.filter(is_active=True)
            .select_related("country")
            .prefetch_related(Prefetch("programs", queryset=Program.objects.all()))
        )
        country = self.request.query_params.get("country")
        if country:
            queryset = queryset.filter(country__name__iexact=country)
        return queryset


class FaqViewSet(ReadOnlyPublicViewSet):
    queryset = FaqItem.objects.filter(is_active=True)
    serializer_class = FaqItemSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def fee_quote(request):
    """The application fee for one school, in the applicant's own currency.

    **The fee belongs to the school.** It used to be one flat Naira figure for
    every partner, which would have charged an applicant to UCAM, whose fee is
    150 EUR, the 200,000 NGN a different school asks for. `institution` is the
    slug of the school being applied to, and the amount comes from that row.

    Without a slug it answers with the typical fee across the active partners,
    which is what the marketing pages want; that answer is marked `indicative`
    so nothing mistakes it for a quote.
    """
    name = (request.query_params.get("origin") or "Nigeria").strip()
    origin = (
        OriginCountry.objects.filter(name__iexact=name).first()
        or OriginCountry.objects.filter(name__iexact="Nigeria").first()
    )

    slug = (request.query_params.get("institution") or "").strip()
    institution = Institution.objects.filter(slug=slug, is_active=True).first() if slug else None

    if institution is not None:
        fee_ngn = institution.application_fee_ngn
        indicative = False
    else:
        # The commonest fee among active partners, so the figure on a page that
        # has not asked about a school is one a real applicant would see.
        fees = [
            i.application_fee_ngn
            for i in Institution.objects.filter(is_active=True).exclude(application_fee=0)
        ]
        fee_ngn = max(set(fees), key=fees.count) if fees else APPLICATION_FEE_NGN
        indicative = True

    gateway_fee_ngn = processing_fee_ngn(fee_ngn)

    if origin is None:
        currency, symbol, rate = "NGN", "₦", Decimal("1")
        amount, processing = fee_ngn, gateway_fee_ngn
    else:
        currency, symbol, rate = origin.currency, origin.symbol, origin.ngn_per_unit
        amount = origin.convert_from_ngn(fee_ngn)
        processing = origin.convert_from_ngn(gateway_fee_ngn)

    return Response(
        {
            "origin": origin.name if origin else name,
            "currency": currency,
            "symbol": symbol,
            "amount": float(amount),
            "amount_ngn": float(fee_ngn),
            # The gateway's cut, worked out in Naira and then converted exactly as
            # the fee is, so the preview adds up to what the card is debited.
            "processing_fee": float(processing),
            "processing_fee_ngn": float(gateway_fee_ngn),
            "rate": float(rate),
            "institution": institution.name if institution else "",
            "institution_slug": institution.slug if institution else "",
            # What the school itself charges, before any conversion.
            "institution_fee": float(institution.application_fee) if institution else None,
            "institution_fee_currency": institution.application_fee_currency if institution else "",
            "deposit_note": institution.deposit_note if institution else "",
            "waived": bool(institution and institution.is_fee_free),
            # True when no school was named, so this is a typical figure rather
            # than a quote for anybody in particular.
            "indicative": indicative,
        }
    )


class ProgramViewSet(ReadOnlyPublicViewSet):
    """Every programme on the platform, searchable across all partners."""

    serializer_class = ProgramCatalogSerializer
    pagination_class = PageNumberPagination
    search_fields = ("name", "institution__name", "institution__location", "qualification_level")
    ordering_fields = ("name", "tuition", "institution__name")
    ordering = ("institution__name", "display_order", "name")

    def get_queryset(self):
        queryset = Program.objects.filter(institution__is_active=True).select_related(
            "institution", "institution__country"
        )

        params = self.request.query_params
        country = params.get("country")
        level = params.get("level")
        institution = params.get("institution")
        fee_free = params.get("fee_free")

        if country and country != "all":
            queryset = queryset.filter(institution__country__name__iexact=country)
        if level and level != "all":
            queryset = queryset.filter(level=level)
        if institution:
            queryset = queryset.filter(institution__slug=institution)
        if fee_free == "true":
            queryset = queryset.filter(institution__application_fee=0)

        return queryset

    @action(detail=False, methods=["get"])
    def levels(self, request):
        """The levels actually in use, with counts, for the filter bar."""
        counts = (
            Program.objects.filter(institution__is_active=True)
            .values("level")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        labels = dict(Program.Level.choices)
        return Response(
            [
                {"value": row["level"], "label": labels.get(row["level"], row["level"]), "count": row["total"]}
                for row in counts
            ]
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def exchange_rates(request):
    """Live exchange rates for the converter.

    ``base`` picks the currency everything is quoted against and defaults to the
    Naira. It must be a three-letter code. ``refresh=true`` skips the cache, and
    only staff may ask for that: open to everyone, it let anyone force a slow
    call to the rate provider on every request.
    """
    import re

    base = (request.query_params.get("base") or "NGN").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", base):
        return Response({"detail": "Use a three-letter currency code."}, status=400)
    force = request.query_params.get("refresh") == "true" and bool(
        request.user and request.user.is_staff
    )
    return Response(get_rates(base, force=force))



# ── Caching ──────────────────────────────────────────────────────────
#
# The catalogue changes a few times a week and is read on every visit, so its
# answers are cached for a few minutes. Any save or delete of a country, school
# or course bumps the version, so the next request after an edit is fresh.

CATALOG_TTL = 300


def catalog_version():
    from django.core.cache import cache

    return cache.get_or_set("catalog:version", 1, None)


def bump_catalog_version(**kwargs):
    from django.core.cache import cache

    try:
        cache.incr("catalog:version")
    except ValueError:
        cache.set("catalog:version", 2, None)


def cached_catalog(view_func):
    """Cache a public GET answer by its full address and the catalogue version."""
    from functools import wraps

    from django.core.cache import cache

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        raw = getattr(request, "_request", request)
        key = f"catalog:{catalog_version()}:{raw.get_full_path()}"
        hit = cache.get(key)
        if hit is not None:
            response = Response(hit)
        else:
            response = view_func(request, *args, **kwargs)
            if getattr(response, "status_code", 500) == 200:
                cache.set(key, response.data, CATALOG_TTL)
        response["Cache-Control"] = "public, max-age=60"
        return response

    return wrapper
