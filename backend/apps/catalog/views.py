from django.db.models import Count, Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.applications.constants import APPLICATION_FEE_NGN, PROCESSING_FEE

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
    permission_classes = (AllowAny,)
    pagination_class = None


class OriginCountryViewSet(ReadOnlyPublicViewSet):
    queryset = OriginCountry.objects.all()
    serializer_class = OriginCountrySerializer
    search_fields = ("name", "currency")


class DestinationCountryViewSet(ReadOnlyPublicViewSet):
    queryset = DestinationCountry.objects.filter(is_active=True)
    serializer_class = DestinationCountrySerializer


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
    """The application fee in the applicant's own currency.

    The fee is always the same amount of Naira. The origin country decides only
    what currency it is displayed in, and the Naira figure is returned alongside
    so the conversion stays checkable.
    """

    name = (request.query_params.get("origin") or "Nigeria").strip()
    origin = OriginCountry.objects.filter(name__iexact=name).first()
    if origin is None:
        origin = OriginCountry.objects.filter(name__iexact="Nigeria").first()

    if origin is None:
        return Response(
            {
                "origin": name,
                "currency": "NGN",
                "symbol": "₦",
                "amount": float(APPLICATION_FEE_NGN),
                "amount_ngn": float(APPLICATION_FEE_NGN),
                "processing_fee": float(PROCESSING_FEE),
                "rate": 1.0,
            }
        )

    amount = origin.convert_from_ngn(APPLICATION_FEE_NGN)
    return Response(
        {
            "origin": origin.name,
            "currency": origin.currency,
            "symbol": origin.symbol,
            "amount": float(amount),
            "amount_ngn": float(APPLICATION_FEE_NGN),
            "processing_fee": float(PROCESSING_FEE),
            "rate": float(origin.ngn_per_unit),
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
    Naira. ``refresh=true`` skips the cache, which is what the converter's
    refresh button sends.
    """
    base = request.query_params.get("base", "NGN")
    force = request.query_params.get("refresh") == "true"
    return Response(get_rates(base, force=force))
