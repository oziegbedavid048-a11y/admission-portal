from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import DestinationCountry, Institution, OriginCountry, Program
from apps.catalog.serializers import InstitutionListSerializer, ProgramSerializer

from .models import (
    Application,
    ApplicationDraft,
    ApplicationDraftFile,
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
            "review_note",
            "uploaded_at",
        )
        read_only_fields = ("id", "status", "review_note", "uploaded_at", "human_size")

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

    def validate_evidence(self, value):
        """Evidence is a document like any other: PDF or image, checked by
        extension, declared type and first bytes. Without this an HTML or SVG
        file could be stored and opened by the desk as a page."""
        from django.conf import settings

        from .uploads import validate_upload

        return validate_upload(value, settings.MAX_UPLOAD_SIZE_MB)


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
    # One fee covers up to three schools: the 1st choice holds the payment.
    fee_reference = serializers.CharField(source="fee_owner.reference", read_only=True)
    fee_schools = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id",
            "reference",
            "choice_order",
            "fee_reference",
            "fee_schools",
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
            "is_custom_course",
            "custom_course_name",
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
        """The fee's payment, held on the 1st choice for every school it covers."""
        from apps.payments.serializers import PaymentSerializer

        payment = obj.fee_payment
        return PaymentSerializer(payment).data if payment else None

    def get_fee_schools(self, obj):
        owner = obj.fee_owner
        schools = [owner, *sorted(owner.covered_applications.all(), key=lambda app: (app.choice_order, app.pk))]
        return [
            {
                "reference": app.reference,
                "choice_order": app.choice_order,
                "institution": app.institution.name if app.institution else app.custom_course_name,
            }
            for app in schools
        ]


class ApplicationContactSerializer(serializers.ModelSerializer):
    """The three fields an applicant may edit themselves after submitting."""

    class Meta:
        model = Application
        fields = ("phone", "address", "grade_gpa")


def _country_name(value, empty_message):
    """A country name as a person would type it: letters, spaces and a few
    marks, nothing else, at most 60 characters."""
    import re

    name = " ".join(str(value or "").split())
    if not name:
        raise serializers.ValidationError(empty_message)
    if len(name) > 60 or not re.fullmatch(r"[^\W\d_][\w .'()&-]*", name, flags=re.UNICODE) or any(
        ch.isdigit() for ch in name
    ):
        raise serializers.ValidationError("Choose a country from the list.")
    return name


MAX_COURSES_PER_APPLICATION = 2
# Besides the 1st choice: a 2nd (included in the fee) and a 3rd (extra).
MAX_EXTRA_CHOICES = 2


def open_application_at(applicant, institution):
    """The applicant's live application at this school, if there is one.

    A second school is a second application with its own fee, but the same
    school twice is not: further courses there belong on the first file. A
    rejected file does not count, so the applicant may try that school again.
    """
    if applicant is None or institution is None:
        return None
    return (
        Application.objects.filter(applicant=applicant, institution=institution)
        .exclude(status=Application.Status.REJECTED)
        .first()
    )


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

    institution = serializers.CharField(
        help_text="Institution slug.", required=False, allow_blank=True, default=""
    )
    program_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    is_custom_course = serializers.BooleanField(required=False, default=False)
    custom_course_name = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    gateway = serializers.CharField(max_length=40, required=False, default="Paystack")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # A 2nd and optionally a 3rd choice school, paid for under this one fee:
    # [{"institution": "<slug>", "program_ids": [..]}]. The 2nd is included in
    # the fee; a 3rd adds EXTRA_SCHOOL_FEE_NGN.
    extra_choices = serializers.ListField(
        child=serializers.DictField(), required=False, default=list, max_length=MAX_EXTRA_CHOICES
    )

    def validate_origin_country(self, value):
        """A country from the list, or a new one added quietly.

        A country not yet on file is added priced in Naira. It used to be added
        as US dollars at a fixed rate, and fee quotes read the dollar rate from
        the first USD country by name, so a made-up country such as "Aaa"
        would have set the dollar rate for every USD-priced school.
        """
        name = _country_name(value, "Choose a country of origin from the list.")
        country = OriginCountry.objects.filter(name__iexact=name).first()
        if country is None:
            country = OriginCountry.objects.create(
                name=name,
                currency="NGN",
                symbol="₦",
                ngn_per_unit=Decimal("1"),
            )
        return country

    def validate_destination_country(self, value):
        name = _country_name(value, "Choose a destination country.")
        country = DestinationCountry.objects.filter(name__iexact=name).first()
        if country is None:
            code = "".join(c for c in name if c.isalnum())[:3].upper() or "DST"
            # Hidden until the desk reviews it, so a name typed by an applicant
            # never appears in the public list of destinations.
            country = DestinationCountry.objects.create(
                name=name,
                code=code,
                currency="USD",
                currency_symbol="$",
                is_active=False,
            )
        return country

    def validate_institution(self, value):
        if not value:
            return None
        institution = Institution.objects.filter(slug=value, is_active=True).first()
        if institution is None:
            raise serializers.ValidationError("Choose a partner institution.")
        return institution

    def validate(self, attrs):
        is_custom = attrs.get("is_custom_course", False)
        if is_custom:
            custom_name = attrs.get("custom_course_name", "").strip()
            if not custom_name:
                raise serializers.ValidationError(
                    {"custom_course_name": "Please specify the course you want to study."}
                )
            if attrs.get("extra_choices"):
                raise serializers.ValidationError(
                    {"extra_choices": "A 2nd or 3rd choice school can only be added to a partner school application."}
                )
            attrs["institution"] = None
            attrs["programs"] = []
            attrs["extra"] = []
            return attrs

        institution = attrs.get("institution")
        if not institution:
            raise serializers.ValidationError({"institution": "Choose a partner institution."})
        # The courses are chosen by the applicant, never filled in for them:
        # one application covers up to two courses at the same school, under
        # one application fee, and the school decides which one to offer.
        program_ids = list(dict.fromkeys(attrs.get("program_ids") or []))
        if not program_ids:
            raise serializers.ValidationError({"program_ids": "Select at least one course."})
        if len(program_ids) > MAX_COURSES_PER_APPLICATION:
            raise serializers.ValidationError(
                {
                    "program_ids": f"You can select a maximum of {MAX_COURSES_PER_APPLICATION} "
                    "courses per institution."
                }
            )
        programs = list(Program.objects.filter(id__in=program_ids, institution=institution))
        if len(programs) != len(program_ids):
            raise serializers.ValidationError(
                {"program_ids": "Choose courses offered by the selected institution."}
            )
        order = {pid: index for index, pid in enumerate(program_ids)}
        programs.sort(key=lambda program: order[program.id])
        dest = attrs.get("destination_country")
        if (
            dest
            and institution.country_id
            and dest.id != institution.country_id
            and institution.country
            and institution.country.name.strip().lower() != dest.name.strip().lower()
        ):
            raise serializers.ValidationError(
                {"institution": "That institution is not in the chosen destination country."}
            )
        attrs["programs"] = programs
        attrs["extra"] = self._extra_choices(attrs, institution)
        return attrs

    def _extra_choices(self, attrs, first_institution):
        """The 2nd and 3rd choice schools, checked like the 1st."""
        chosen = attrs.get("extra_choices") or []
        resolved = []
        seen = {first_institution.pk}
        for position, raw in enumerate(chosen, start=2):
            label = "2nd" if position == 2 else "3rd"
            slug = str(raw.get("institution") or "").strip()
            school = Institution.objects.filter(slug=slug, is_active=True).select_related("country").first()
            if school is None:
                raise serializers.ValidationError({"extra_choices": f"Choose a partner institution for your {label} choice."})
            if school.pk in seen:
                raise serializers.ValidationError({"extra_choices": "Choose a different school for each choice."})
            seen.add(school.pk)
            try:
                ids = list(dict.fromkeys(int(pid) for pid in (raw.get("program_ids") or [])))
            except (TypeError, ValueError):
                raise serializers.ValidationError({"extra_choices": f"Choose the courses for your {label} choice."})
            if not ids:
                raise serializers.ValidationError({"extra_choices": f"Select at least one course for your {label} choice."})
            if len(ids) > MAX_COURSES_PER_APPLICATION:
                raise serializers.ValidationError(
                    {"extra_choices": f"You can select a maximum of {MAX_COURSES_PER_APPLICATION} courses per institution."}
                )
            courses = list(Program.objects.filter(id__in=ids, institution=school))
            if len(courses) != len(ids):
                raise serializers.ValidationError(
                    {"extra_choices": f"Choose courses offered by your {label} choice school."}
                )
            order = {pid: index for index, pid in enumerate(ids)}
            courses.sort(key=lambda course: order[course.id])
            resolved.append((school, courses))
        return resolved

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        agent_profile = getattr(user, "agent_profile", None)
        is_custom = validated_data.get("is_custom_course", False)
        custom_name = (
            validated_data.get("custom_course_name", "").strip() if is_custom else ""
        )

        applicant = validated_data.pop("applicant", user)
        agent = validated_data.pop("agent", agent_profile)
        extra = validated_data.pop("extra", [])
        for school in [validated_data.get("institution"), *(choice[0] for choice in extra)]:
            existing = open_application_at(applicant, school)
            if existing is not None:
                raise serializers.ValidationError(
                    {
                        "institution": f"An application to {existing.institution.name} already exists "
                        f"({existing.reference}). Choose a different school."
                    }
                )
        # Every email about a file goes to this address. For an applicant's own
        # file it is their account address, never one typed into the form:
        # otherwise anyone could have Gabstep mail any inbox they liked.
        email = validated_data["email"] if agent else applicant.email

        application = Application.objects.create(
            applicant=applicant,
            submitted_by_agent=agent,
            full_name=validated_data["full_name"],
            email=email,
            phone=validated_data["phone"],
            address=validated_data["origin_country"].name,
            origin_country=validated_data["origin_country"],
            destination_country=validated_data["destination_country"],
            previous_schools=validated_data["previous_schools"],
            qualification=validated_data["qualification"],
            year_graduated=validated_data["year_graduated"],
            grade_gpa=validated_data["grade_gpa"],
            institution=validated_data.get("institution"),
            is_custom_course=is_custom,
            custom_course_name=custom_name,
            welcome_email_sent=bool(is_custom),
            notes=validated_data.get("notes", ""),
            status=Application.Status.SUBMITTED,
        )
        if not is_custom and validated_data.get("programs"):
            application.programs.set(validated_data["programs"])
        application.build_default_stages()

        # The 2nd and 3rd choices: their own files, paid for under this one.
        for order, (school, courses) in enumerate(extra, start=2):
            covered = Application.objects.create(
                applicant=applicant,
                submitted_by_agent=agent,
                fee_parent=application,
                choice_order=order,
                full_name=application.full_name,
                email=application.email,
                phone=application.phone,
                address=application.address,
                origin_country=application.origin_country,
                destination_country=school.country,
                previous_schools=application.previous_schools,
                qualification=application.qualification,
                year_graduated=application.year_graduated,
                grade_gpa=application.grade_gpa,
                institution=school,
                notes=application.notes,
                status=Application.Status.SUBMITTED,
            )
            covered.programs.set(courses)
            covered.build_default_stages()
            choice = "2nd" if order == 2 else "3rd"
            Notification.objects.create(
                application=covered,
                text=f"Application submitted for {school.name}, your {choice} choice, "
                f"under the fee for {application.reference}.",
                send_email=False,
            )

        target_name = custom_name or (
            application.institution.name
            if application.institution
            else application.destination_country.name
        )
        Notification.objects.create(
            application=application,
            text=f"Application submitted for {target_name}.",
            send_email=False,
        )
        # One confirmation email for the submission, sent once the application
        # and its courses are saved.
        from apps.accounts.emails import send_application_received_email

        transaction.on_commit(lambda: send_application_received_email(application))
        return application


class ApplicationDraftFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationDraftFile
        fields = ("id", "slot", "kind", "name", "original_filename", "uploaded_at")
        read_only_fields = fields


class ApplicationDraftSerializer(serializers.ModelSerializer):
    files = ApplicationDraftFileSerializer(many=True, read_only=True)

    class Meta:
        model = ApplicationDraft
        fields = ("current_step", "data", "files", "saved_at")
        read_only_fields = ("files", "saved_at")
