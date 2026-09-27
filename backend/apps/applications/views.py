from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Application,
    ApplicationDraft,
    CorrectionRequest,
    Document,
    Letter,
    Notification,
    Stage,
)
from .serializers import (
    ApplicationContactSerializer,
    ApplicationCreateSerializer,
    ApplicationDraftSerializer,
    ApplicationSerializer,
    CorrectionRequestSerializer,
    DocumentSerializer,
    NotificationSerializer,
)


def visible_applications(user):
    """What this user is allowed to see.

    Staff see everything, an agent sees the files they filed, and an applicant
    sees only their own.
    """
    queryset = (
        Application.objects.select_related(
            "institution", "institution__country", "origin_country", "destination_country"
        )
        .prefetch_related(
            "programs",
            Prefetch("stages", queryset=Stage.objects.all()),
            Prefetch("documents", queryset=Document.objects.all()),
            Prefetch("notifications", queryset=Notification.objects.all()),
            Prefetch("letters", queryset=Letter.objects.filter(is_published=True)),
            "corrections",
        )
    )
    if user.is_staff:
        return queryset
    agent_profile = getattr(user, "agent_profile", None)
    if agent_profile is not None:
        return queryset.filter(submitted_by_agent=agent_profile)
    return queryset.filter(applicant=user)


class ApplicationViewSet(viewsets.ModelViewSet):
    """Applicant files. Create runs the whole wizard submission in one call."""

    serializer_class = ApplicationSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    http_method_names = ("get", "post", "patch", "head", "options")
    lookup_field = "reference"
    search_fields = ("reference", "full_name", "email", "institution__name")
    filterset_fields = ("status", "visa_status")

    def get_queryset(self):
        return visible_applications(self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationCreateSerializer
        if self.action == "partial_update":
            return ApplicationContactSerializer
        return ApplicationSerializer

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            application = serializer.save()
            ApplicationDraft.objects.filter(user=request.user).delete()
            return Response(
                ApplicationSerializer(application, context=self.get_serializer_context()).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            import logging, traceback
            from rest_framework.exceptions import ValidationError
            if isinstance(exc, ValidationError):
                raise
            logging.getLogger(__name__).error("Failed creating application: %s\n%s", exc, traceback.format_exc())
            return Response(
                {"detail": f"Application submission error: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def partial_update(self, request, *args, **kwargs):
        application = self.get_object()
        serializer = ApplicationContactSerializer(
            application, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            ApplicationSerializer(application, context=self.get_serializer_context()).data
        )

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """The signed-in applicant's most recent file, or 404 if they have none."""
        application = visible_applications(request.user).filter(
            applicant=request.user
        ).first()
        if application is None:
            return Response(
                {"detail": "No application found for this account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            ApplicationSerializer(application, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], parser_classes=(MultiPartParser, FormParser))
    def documents(self, request, reference=None):
        application = self.get_object()
        serializer = DocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(application=application)
        # Three documents go up one after another during the wizard, so these
        # stay in the feed but do not each become an email.
        Notification.objects.create(
            application=application,
            text=f"{document.name} uploaded and queued for review.",
            send_email=False,
        )
        return Response(
            DocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"])
    def corrections(self, request, reference=None):
        application = self.get_object()
        if request.method == "GET":
            return Response(
                CorrectionRequestSerializer(
                    application.corrections.all(), many=True
                ).data
            )
        serializer = CorrectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correction = serializer.save(application=application)
        Notification.objects.create(
            application=application,
            text=f"Correction to {correction.field} logged as {correction.ticket}.",
        )
        return Response(
            CorrectionRequestSerializer(correction).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="notifications/read")
    def mark_notifications_read(self, request, reference=None):
        application = self.get_object()
        application.notifications.filter(is_read=False).update(is_read=True)
        return Response(
            NotificationSerializer(application.notifications.all(), many=True).data
        )

    @action(detail=True, methods=["post"], url_path="transfer-to-visa-support")
    def transfer_to_visa_support(self, request, reference=None):
        application = self.get_object()
        application.transferred_to_visa_support = True
        if not application.transferred_to_visa_support_at:
            application.transferred_to_visa_support_at = timezone.now()
        if application.visa_status == Application.VisaStatus.NOT_STARTED:
            application.visa_status = Application.VisaStatus.IN_PROGRESS
        application.save(
            update_fields=[
                "transferred_to_visa_support",
                "transferred_to_visa_support_at",
                "visa_status",
                "updated_at",
            ]
        )
        Notification.objects.create(
            application=application,
            text="Application file and admission letter transferred to Visa Support Assistant desk. An advisor has been assigned to your visa file.",
        )
        return Response(
            ApplicationSerializer(application, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class DraftView(APIView):
    """The wizard's save-and-continue-later slot: one draft per user."""

    def get(self, request):
        draft = ApplicationDraft.objects.filter(user=request.user).first()
        if draft is None:
            return Response({"detail": "No saved draft."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ApplicationDraftSerializer(draft).data)

    def put(self, request):
        draft, _ = ApplicationDraft.objects.get_or_create(user=request.user)
        serializer = ApplicationDraftSerializer(draft, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request):
        ApplicationDraft.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
