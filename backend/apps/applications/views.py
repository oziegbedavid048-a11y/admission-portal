from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttles import UploadThrottle, UserThrottle

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
from .serializers import (
    ApplicationDraftFileSerializer,
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
            # Documents saved with the draft become the application's documents.
            draft = ApplicationDraft.objects.filter(user=request.user).first()
            if draft is not None:
                from django.core.files.base import ContentFile

                for item in draft.files.all():
                    item.file.open("rb")
                    try:
                        content = item.file.read()
                    finally:
                        item.file.close()
                    Document.objects.create(
                        application=application,
                        kind=item.kind,
                        name=item.name,
                        original_filename=item.original_filename,
                        file=ContentFile(content, name=item.original_filename or "document"),
                    )
                draft.delete()
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
            # The details are in the log. The reply says only that it failed:
            # an exception's text can carry database and server internals.
            return Response(
                {"detail": "Your application could not be submitted. Please try again."},
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

    @action(
        detail=True,
        methods=["post"],
        parser_classes=(MultiPartParser, FormParser),
        throttle_classes=(UserThrottle, UploadThrottle),
    )
    def documents(self, request, reference=None):
        from .uploads import MAX_DOCUMENTS_PER_APPLICATION, check_room

        application = self.get_object()
        check_room(application.documents.count(), MAX_DOCUMENTS_PER_APPLICATION, "documents")
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

    @action(detail=True, methods=["get", "post"], throttle_classes=(UserThrottle, UploadThrottle))
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

    @action(
        detail=True,
        methods=["post"],
        url_path=r"documents/(?P<document_id>[0-9]+)/replace",
        parser_classes=(MultiPartParser, FormParser),
        throttle_classes=(UserThrottle, UploadThrottle),
    )
    def replace_document(self, request, reference=None, document_id=None):
        """Upload a new copy of one document, usually after it was rejected.

        The same document keeps its place on the file; its old copy is removed,
        it goes back to Pending review, and the reviewer's note is cleared.
        """
        from django.conf import settings
        from django.shortcuts import get_object_or_404

        from .uploads import validate_upload

        application = self.get_object()
        document = get_object_or_404(application.documents, pk=document_id)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": ["Choose a file to upload."]}, status=status.HTTP_400_BAD_REQUEST)
        validate_upload(upload, settings.MAX_UPLOAD_SIZE_MB)

        document.file = upload
        document.original_filename = upload.name
        document.status = Document.Status.PENDING
        document.review_note = ""
        document.reviewed_at = None
        document.reviewed_by = None
        document.save()
        Notification.objects.create(
            application=application,
            text=f"{document.name} replaced and queued for review.",
            send_email=False,
        )
        from . import services

        services.sync_documents_checkpoint(application)
        return Response(DocumentSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="transfer-to-visa-support")
    def transfer_to_visa_support(self, request, reference=None):
        """The applicant sends their letter to the Visa Support desk.

        One job: put the file in the desk's queue. The desk decides when visa
        work starts. Only possible once a letter has been issued, and pressing
        it twice changes nothing and sends nothing.
        """
        application = self.get_object()
        if not application.letters.filter(is_published=True).exists():
            return Response(
                {"detail": "Your letter has not been issued yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not application.transferred_to_visa_support:
            application.transferred_to_visa_support = True
            application.transferred_to_visa_support_at = timezone.now()
            application.save(
                update_fields=["transferred_to_visa_support", "transferred_to_visa_support_at", "updated_at"]
            )
            Notification.objects.create(
                application=application,
                text="Your letter was sent to our Visa Support desk. An advisor will contact you about your visa.",
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


class DraftFileView(APIView):
    """Add or replace one document on the applicant's draft, or remove one."""

    parser_classes = (MultiPartParser, FormParser)

    throttle_classes = (UserThrottle, UploadThrottle)

    def post(self, request):
        from django.conf import settings

        from .uploads import validate_upload

        upload = request.FILES.get("file")
        slot = (request.data.get("slot") or "").strip()[:24]
        name = (request.data.get("name") or "").strip()[:160]
        kind = (request.data.get("kind") or "other").strip()[:16]
        if upload is None or not slot or not name:
            return Response(
                {"detail": "A file, its slot and its name are all needed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        validate_upload(upload, settings.MAX_UPLOAD_SIZE_MB)
        draft, _ = ApplicationDraft.objects.get_or_create(user=request.user)
        item = draft.files.filter(slot=slot).first()
        if item is None:
            # A new slot is a new file; replacing one in place is always allowed.
            from .uploads import MAX_FILES_PER_DRAFT, check_room

            check_room(draft.files.count(), MAX_FILES_PER_DRAFT)
            item = ApplicationDraftFile(draft=draft, slot=slot)
        item.kind = kind if kind in {"passport", "academic", "cv", "other"} else "other"
        item.name = name
        item.file = upload
        item.original_filename = upload.name
        item.save()
        draft.save(update_fields=["saved_at"])
        return Response(ApplicationDraftFileSerializer(item).data, status=status.HTTP_201_CREATED)

    def delete(self, request, file_id=None):
        deleted, _ = ApplicationDraftFile.objects.filter(pk=file_id, draft__user=request.user).delete()
        if not deleted:
            return Response({"detail": "No such file on your draft."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
