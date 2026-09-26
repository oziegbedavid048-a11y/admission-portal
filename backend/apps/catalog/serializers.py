from rest_framework import serializers

from .models import (
    DestinationCountry,
    FaqItem,
    Institution,
    OriginCountry,
    Program,
)


class OriginCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = OriginCountry
        fields = ("id", "name", "currency", "symbol", "ngn_per_unit")


class DestinationCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DestinationCountry
        fields = ("id", "name", "code", "currency", "currency_symbol", "is_european")


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = (
            "id",
            "name",
            "level",
            "duration",
            "qualification_level",
            "tuition",
            "intake",
            "note",
            "scholarship",
        )


class InstitutionSerializer(serializers.ModelSerializer):
    programs = ProgramSerializer(many=True, read_only=True)
    country = serializers.CharField(source="country.name", read_only=True)
    is_fee_free = serializers.BooleanField(read_only=True)

    class Meta:
        model = Institution
        fields = (
            "id",
            "slug",
            "name",
            "country",
            "location",
            "tagline",
            "badge",
            "currency",
            "application_fee",
            "is_fee_free",
            "tuition_summary",
            "features",
            "programs",
        )


class InstitutionListSerializer(InstitutionSerializer):
    """Same shape without the programs, for lists that only need the header."""

    class Meta(InstitutionSerializer.Meta):
        fields = tuple(f for f in InstitutionSerializer.Meta.fields if f != "programs")


class FaqItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqItem
        fields = ("id", "question", "answer")


class ProgramCatalogSerializer(serializers.ModelSerializer):
    """A programme with enough of its institution attached to stand alone.

    The agent's course browser lists programmes across every partner, so each
    row has to say where it is taught without a second lookup.
    """

    level_display = serializers.CharField(source="get_level_display", read_only=True)
    institution = serializers.CharField(source="institution.name", read_only=True)
    institution_slug = serializers.CharField(source="institution.slug", read_only=True)
    location = serializers.CharField(source="institution.location", read_only=True)
    country = serializers.CharField(source="institution.country.name", read_only=True)
    currency = serializers.CharField(source="institution.currency", read_only=True)
    application_fee = serializers.DecimalField(
        source="institution.application_fee", max_digits=10, decimal_places=2, read_only=True
    )
    is_fee_free = serializers.BooleanField(source="institution.is_fee_free", read_only=True)
    badge = serializers.CharField(source="institution.badge", read_only=True)

    class Meta:
        model = Program
        fields = (
            "id",
            "name",
            "level",
            "level_display",
            "duration",
            "qualification_level",
            "tuition",
            "intake",
            "note",
            "scholarship",
            "institution",
            "institution_slug",
            "location",
            "country",
            "currency",
            "application_fee",
            "is_fee_free",
            "badge",
        )
        read_only_fields = fields
