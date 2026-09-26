from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program
from apps.catalog.serializers import InstitutionListSerializer, ProgramSerializer

from .models import (
    Application,
    ApplicationDraft,
    CorrectionRequest,
    Document,
    Letter,
    Notification,
    Stage,
)


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = ("id", "order", "name", "note", "eta", "status")


class DocumentSerializer(serializers.ModelSerializer):
    human_size = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "kind",
            "name",
            "file",
            "original_filename",
            "size_bytes",
            "human_size",
            "status",
            "uploaded_at",
        )
        read_only_fields = ("id", "status", "uploaded_at", "human_size")

    def validate_file(self, value):
        from django.conf import settings

        from .uploads import validate_upload

        return validate_upload(value, settings.MAX_UPLOAD_SIZE_MB)

    def create(self, validated_data):
        uploaded = validated_data.get("file")
        if uploaded is not None:
            validated_data.setdefault("original_filename", uploaded.name)
            validated_data["size_bytes"] = uploaded.size
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "text", "is_read", "created_at")
        read_only_fields = ("id", "created_at")


class CorrectionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorrectionRequest
        fields = (
            "id",
            "ticket",
            "field",
            "current_value",
            "corrected_value",
            "reason",
            "evidence",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "ticket", "status", "created_at")


class LetterSerializer(serializers.ModelSerializer):
    """An official letter issued to the applicant, as their dashboard lists it."""

    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    filename = serializers.CharField(read_only=True)

    class Meta:
        model = Letter
        fields = (
            "id",
            "kind",
            "kind_display",
            "title",
            "file",
            "filename",
            "note",
            "issued_at",
        )
        read_only_fields = fields


class ApplicationSerializer(serializers.ModelSerializer):
    """The full applicant file, as the dashboard reads it."""

    institution = InstitutionListSerializer(read_only=True)
    programs = ProgramSerializer(many=True, read_only=True)
    origin_country = serializers.CharField(source="origin_country.name", read_only=True)
    destination_country = serializers.CharField(
        source="destination_country.name", read_only=True
    )
    stages = StageSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    notifications = NotificationSerializer(many=True, read_only=True)
    corrections = CorrectionRequestSerializer(many=True, read_only=True)
    letters = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    current_stage_index = serializers.IntegerField(read_only=True)
    verification_status_display = serializers.CharField(
        source="get_verification_status_display", read_only=True
    )
    verification_summary = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "reference",
            "full_name",
            "email",
            "phone",
            "address",
            "origin_country",
            "destination_country",
            "previous_schools",
            "qualification",
            "year_graduated",
            "grade_gpa",
            "institution",
            "programs",
            "status",
            "visa_status",
            "transferred_to_visa_support",
            "transferred_to_visa_support_at",
            "verification_status",
            "verification_status_display",
            "personal_details_verified",
            "academic_details_verified",
            "documents_verified",
            "payment_verified",
            "verified_at",
            "verification_notes",
            "verification_summary",
            "notes",
            "submitted_at",
            "stages",
            "documents",
            "notifications",
            "corrections",
            "letters",
            "payment",
            "current_stage_index",
        )
        read_only_fields = fields

    def get_verification_summary(self, obj):
        return obj.verification_summary

    def get_letters(self, obj):
        """Only published letters. A staged one is not news until staff say so."""
        published = [letter for letter in obj.letters.all() if letter.is_published]
        return LetterSerializer(published, many=True, context=self.context).data

    def get_payment(self, obj):
        from apps.payments.serializers import PaymentSerializer

        payment = getattr(obj, "payment", None)
        return PaymentSerializer(payment).data if payment else None


class ApplicationContactSerializer(serializers.ModelSerializer):
    """The three fields an applicant may edit themselves after submitting."""

    class Meta:
        model = Application
        fields = ("phone", "address", "grade_gpa")


class ApplicationCreateSerializer(serializers.Serializer):
    """Everything the five-step wizard collects, submitted in one call."""

    full_name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40)
    origin_country = serializers.CharField(max_length=80)
    destination_country = serializers.CharField(max_length=80)

    previous_schools = serializers.CharField(max_length=250)
    qualification = serializers.CharField(max_length=40)
    year_graduated = serializers.IntegerField(min_value=1960, max_value=2035)
    grade_gpa = serializers.CharField(max_length=120)

    institution = serializers.CharField(help_text="Institution slug.")
    program_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=2
    )

    gateway = serializers.CharField(max_length=40, required=False, default="Paystack")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_origin_country(self, value):
        country = OriginCountry.objects.filter(name__iexact=value).first()
        if country is None:
            raise serializers.ValidationError("Choose a country of origin from the list.")
        return country

    def validate_destination_country(self, value):
        country = DestinationCountry.objects.filter(
            name__iexact=value, is_active=True
        ).first()
        if country is None:
            raise serializers.ValidationError("Choose a destination country from the list.")
        return country

    def validate_institution(self, value):
        institution = Institution.objects.filter(slug=value, is_active=True).first()
        if institution is None:
            raise serializers.ValidationError("Choose a partner institution.")
        return institution

    def validate(self, attrs):
        institution = attrs["institution"]
        programs = list(Program.objects.filter(id__in=attrs["program_ids"]))
        if not programs:
            raise serializers.ValidationError(
                {"program_ids": "Select at least one course."}
            )
        if len(programs) > 2:
            raise serializers.ValidationError(
                {"program_ids": "You can select a maximum of 2 courses per institution."}
            )
        wrong = [p for p in programs if p.institution_id != institution.id]
        if wrong:
            raise serializers.ValidationError(
                {"program_ids": "Every course must belong to the chosen institution."}
            )
        if attrs["destination_country"].id != institution.country_id:
            raise serializers.ValidationError(
                {"institution": "That institution is not in the chosen destination country."}
            )
        attrs["programs"] = programs
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        agent_profile = getattr(user, "agent_profile", None)

        application = Application.objects.create(
            applicant=validated_data.pop("applicant", user),
            submitted_by_agent=validated_data.pop("agent", agent_profile),
            full_name=validated_data["full_name"],
            email=validated_data["email"],
            phone=validated_data["phone"],
            address=validated_data["origin_country"].name,
            origin_country=validated_data["origin_country"],
            destination_country=validated_data["destination_country"],
            previous_schools=validated_data["previous_schools"],
            qualification=validated_data["qualification"],
            year_graduated=validated_data["year_graduated"],
            grade_gpa=validated_data["grade_gpa"],
            institution=validated_data["institution"],
            notes=validated_data.get("notes", ""),
            status=Application.Status.SUBMITTED,
        )
        application.programs.set(validated_data["programs"])
        application.build_default_stages()
        Notification.objects.create(
            application=application,
            text=f"Application submitted to {application.institution.name}.",
            send_email=False,
        )
        return application


class ApplicationDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationDraft
        fields = ("current_step", "data", "saved_at")
        read_only_fields = ("saved_at",)
