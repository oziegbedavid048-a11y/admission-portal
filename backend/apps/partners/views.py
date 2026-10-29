from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.constants import AGENT_REGISTRATION_COMMISSION_NGN, AGENT_VISA_COMMISSION_NGN
from apps.applications.models import Application
from config.throttles import MoneyThrottle, UploadThrottle, UserThrottle, edge_ip

from .currency import money
from .models import (
    Commission,
    Loan,
    LoanRepayment,
    StudentDraft,
    StudentDraftFile,
    Wallet,
    Withdrawal,
    loan_block_reason,
)
from .permissions import ContractSigned, IsAgent
from .serializers import (
    AgentProfileSerializer,
    AgentStudentCreateSerializer,
    AgentStudentNoteSerializer,
    AgentStudentSerializer,
    CommissionSerializer,
    LoanSerializer,
    PayMetaInvoiceSerializer,
    ReleaseFromSavingsSerializer,
    RepayLoanSerializer,
    StudentDraftFileSerializer,
    StudentDraftSerializer,
    SaveToSavingsSerializer,
    WalletSerializer,
    WithdrawalRequestSerializer,
    WithdrawalSerializer,
)


class AgentScopedMixin:
    permission_classes = (IsAgent, ContractSigned)
    # True on the views an agent who has not signed the contract yet may use.
    contract_exempt = False

    @property
    def agent(self):
        return self.request.user.agent_profile


class AgentProfileView(AgentScopedMixin, RetrieveUpdateAPIView):
    serializer_class = AgentProfileSerializer
    contract_exempt = True
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self):
        return self.agent


class WalletView(AgentScopedMixin, APIView):
    contract_exempt = True

    def get(self, request):
        return Response(WalletSerializer(self.agent.wallet).data)


class WalletHistoryView(AgentScopedMixin, APIView):
    """Every movement of the agent's money, newest first.

    Money in is each commission. Money out is each Ads funding repayment and
    each withdrawal that is in review or paid. A failed withdrawal is left out:
    its amount went back to the balance, so nothing left the wallet.
    """

    LIMIT = 500

    def get(self, request):
        agent = self.agent
        rows = []
        commissions = Commission.objects.filter(agent=agent).select_related("application")[: self.LIMIT]
        for item in commissions:
            rows.append(
                {
                    "id": f"c-{item.pk}",
                    "direction": "in",
                    "title": (
                        "Visa commission"
                        if item.kind == Commission.Kind.VISA
                        else "Registration commission"
                    ),
                    "detail": item.application.full_name,
                    "reference": item.application.reference,
                    "amount": item.amount,
                    "currency": item.currency,
                    "at": item.earned_at,
                    "status": "",
                }
            )
        for item in LoanRepayment.objects.filter(agent=agent)[: self.LIMIT]:
            rows.append(
                {
                    "id": f"r-{item.pk}",
                    "direction": "out",
                    "title": "Ads funding repaid",
                    "detail": "",
                    "reference": "",
                    "amount": item.amount,
                    "currency": item.currency,
                    "at": item.created_at,
                    "status": "",
                }
            )
        withdrawals = Withdrawal.objects.filter(agent=agent).exclude(status=Withdrawal.Status.FAILED)
        for item in withdrawals[: self.LIMIT]:
            rows.append(
                {
                    "id": f"w-{item.pk}",
                    "direction": "out",
                    "title": "Withdrawal",
                    "detail": "",
                    "reference": item.reference,
                    "amount": item.amount_requested,
                    "currency": item.currency,
                    "at": item.created_at,
                    "status": item.status,
                }
            )
        rows.sort(key=lambda row: row["at"], reverse=True)
        rows = rows[: self.LIMIT]
        for row in rows:
            row["amount"] = f"{row['amount']:.2f}"
        return Response(rows)


class WithdrawalViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    serializer_class = WithdrawalSerializer
    http_method_names = ("get", "post", "head", "options")
    pagination_class = None

    def get_queryset(self):
        return Withdrawal.objects.filter(agent=self.agent)

    throttle_classes = (UserThrottle, MoneyThrottle)

    def create(self, request, *args, **kwargs):
        serializer = WithdrawalRequestSerializer(
            data=request.data, context={"agent": self.agent}
        )
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal = Withdrawal.request(self.agent, serializer.validated_data["amount"])
        except DjangoValidationError as exc:
            # Raised inside the row lock, which is the check that actually counts.
            raise drf_serializers.ValidationError({"amount": exc.messages})
        # A Nigerian agent with a verified account is paid through Paystack at once.
        from .payouts import prepare, send

        if prepare(withdrawal):
            withdrawal = send(withdrawal)
        else:
            withdrawal.refresh_from_db()
        return Response(
            {
                "withdrawal": WithdrawalSerializer(withdrawal).data,
                "wallet": WalletSerializer(self.agent.wallet).data,
            },
            status=status.HTTP_201_CREATED,
        )


class SavingsView(AgentScopedMixin, APIView):
    """Move balance into savings, and back out again.

    Saving used to be one-way, which meant anything set aside stopped being
    withdrawable for good. DELETE releases it.
    """

    throttle_classes = (UserThrottle, MoneyThrottle)

    def post(self, request):
        serializer = SaveToSavingsSerializer(
            data=request.data, context={"agent": self.agent}
        )
        serializer.is_valid(raise_exception=True)
        try:
            wallet = self.agent.wallet.move_to_savings(serializer.validated_data["amount"])
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"amount": exc.messages})
        return Response(WalletSerializer(wallet).data)

    def delete(self, request):
        serializer = ReleaseFromSavingsSerializer(
            data=request.data, context={"agent": self.agent}
        )
        serializer.is_valid(raise_exception=True)
        try:
            wallet = self.agent.wallet.release_from_savings(
                serializer.validated_data["amount"]
            )
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"amount": exc.messages})
        return Response(WalletSerializer(wallet).data)


class LoanViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    serializer_class = LoanSerializer
    http_method_names = ("get", "post", "head", "options")
    pagination_class = None

    def get_queryset(self):
        return Loan.objects.filter(agent=self.agent)

    throttle_classes = (UserThrottle, MoneyThrottle)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "agent": self.agent}

    def perform_create(self, serializer):
        # Re-checked with the wallet row locked: two requests sent at the same
        # moment both pass the serializer's check, and only one may be saved.
        with transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            reason = loan_block_reason(self.agent, wallet)
            if reason:
                raise drf_serializers.ValidationError({"detail": reason})
            wallet.sync_currency()
            serializer.save(agent=self.agent, currency=wallet.currency)

    @action(detail=True, methods=["post"], url_path="pay-meta")
    def pay_meta(self, request, pk=None):
        """Pay an approved loan's Meta invoice through Paystack, now."""
        from .loan_payouts import pay_invoice

        loan = self.get_object()
        if not loan.awaiting_invoice:
            raise drf_serializers.ValidationError({"detail": "This funding is not waiting for a Meta invoice."})
        serializer = PayMetaInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = pay_invoice(loan, serializer.validated_data)
        return Response(LoanSerializer(loan).data)

    @action(detail=False, methods=["post"])
    def repay(self, request):
        """Pay back Ads funding from the available balance."""
        serializer = RepayLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet, _ = Wallet.objects.get_or_create(agent=self.agent)
        try:
            wallet = wallet.repay_loan(serializer.validated_data["amount"])
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError({"amount": exc.messages})
        return Response(
            {
                "wallet": WalletSerializer(wallet).data,
                "loans": LoanSerializer(self.get_queryset(), many=True).data,
            }
        )


class AgentStudentViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    """The students this agent has filed applications for."""

    serializer_class = AgentStudentSerializer
    lookup_field = "reference"
    http_method_names = ("get", "post", "patch", "head", "options")
    search_fields = ("full_name", "reference", "institution__name", "email")
    filterset_fields = ("status", "visa_status")
    pagination_class = None

    def get_queryset(self):
        return (
            Application.objects.filter(submitted_by_agent=self.agent)
            .select_related("institution", "origin_country", "destination_country")
            .select_related("payment", "fee_parent", "fee_parent__payment")
            .prefetch_related("programs", "documents", "commissions", "letters")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return AgentStudentCreateSerializer
        if self.action == "partial_update":
            # A PATCH reaches one field: the agent's own note. Status, visa
            # status and the student's contact details belong to the desk.
            return AgentStudentNoteSerializer
        return AgentStudentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        # The sign-in details are emailed to the agent rather than returned
        # here, so a password never sits in a page, a log or a browser cache.
        payload = AgentStudentSerializer(
            application, context=self.get_serializer_context()
        ).data
        payload["account_created"] = getattr(application, "account_created", False)
        # Every school's file (a 2nd and 3rd choice too), so documents can be
        # uploaded to each. The 1st choice holds the one fee for all of them.
        payload["fee_schools"] = [
            {"reference": app.reference, "choice_order": app.choice_order}
            for app in [application, *application.covered_applications.order_by("choice_order")]
        ]
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def stages(self, request, reference=None):
        application = self.get_object()
        return Response(
            [
                {
                    "order": s.order,
                    "name": s.name,
                    "status": s.status,
                    "eta": s.eta,
                    "note": s.note,
                }
                for s in application.stages.all()
            ]
        )


    @action(detail=True, methods=["get"])
    def summary(self, request, reference=None):
        """The one-page student summary PDF. Only once the fee is settled."""
        from django.http import HttpResponse

        from apps.applications.dossier import student_summary_pdf

        application = self.get_object()
        # Ready once the work has started: paid, waived, or a deposit in.
        payment = application.fee_payment
        if payment is None or payment.status not in {"paid", "waived", "part_paid"}:
            return Response(
                {"detail": "The summary is ready once the application fee is confirmed."},
                status=status.HTTP_409_CONFLICT,
            )
        response = HttpResponse(student_summary_pdf(application), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{application.reference}-student-summary.pdf"'
        )
        return response


class AgentCertificateView(AgentScopedMixin, APIView):
    """The agent's partnership certificate, as a PDF.

    Not found until six hours after the account was set up: before then the
    certificate does not exist as far as the portal is concerned.
    """

    def get(self, request):
        from django.http import Http404, HttpResponse

        from .certificate import build_partnership_certificate

        agent = self.agent
        if not agent.certificate_ready:
            raise Http404
        response = HttpResponse(build_partnership_certificate(agent), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="Apply-Gabstep-Partner-Certificate-{agent.partner_code}.pdf"'
        )
        response["Cache-Control"] = "private, no-store"
        return response


class AgentContractView(AgentScopedMixin, APIView):
    """Where the agent stands with the contract, and what goes on it.

    GET answers with the status ("pending", "signed" or "none"), the details
    printed on the contract and, once signed, when and how.
    """

    contract_exempt = True

    def get(self, request):
        from .contract import details_for

        agent = self.agent
        contract = getattr(agent, "contract", None)
        signed = agent.contract_status == "signed"
        return Response(
            {
                "status": agent.contract_status,
                "details": details_for(agent),
                "today": timezone.localdate(),
                "signed_on": contract.signed_on if signed else None,
                "source": contract.source if signed else None,
                "filename": contract.filename if signed else None,
                "content_type": contract.content_type if signed else None,
            }
        )


class AgentContractPreviewView(AgentScopedMixin, APIView):
    """The contract with the agent's details on it, to read before signing."""

    contract_exempt = True

    def get(self, request):
        from django.http import HttpResponse

        from .contract import preview_pdf

        agent = self.agent
        if agent.contract_status == "signed":
            return Response({"detail": "Your contract is already signed."}, status=status.HTTP_409_CONFLICT)
        response = HttpResponse(preview_pdf(agent), content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="Apply-Gabstep-Sales-Partnership-Contract.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class AgentContractSignView(AgentScopedMixin, APIView):
    """Sign the contract: a PNG signature, how it was made, and the address if
    sign-up did not have one."""

    contract_exempt = True
    throttle_classes = (UploadThrottle,)

    def post(self, request):
        from .contract import ContractError, decode_signature, sign

        if request.data.get("agree") not in (True, "true", "1", 1):
            return Response(
                {"detail": "Tick the box to confirm you have read and agree to the contract."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            contract = sign(
                self.agent,
                signature_png=decode_signature(request.data.get("signature")),
                method=request.data.get("method", ""),
                address=request.data.get("address"),
                ip_address=_signing_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ContractError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "status": "signed",
                "signed_on": contract.signed_on,
                "source": contract.source,
                "filename": contract.filename,
                "content_type": contract.content_type,
            },
            status=status.HTTP_201_CREATED,
        )


def _signing_ip(request):
    """The address the contract was signed from, or None if it is not one."""
    import ipaddress

    address = edge_ip(request)
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return None


class AgentContractFileView(AgentScopedMixin, APIView):
    """The signed contract PDF (or the paper contract staff uploaded)."""

    contract_exempt = True

    def get(self, request):
        from django.http import Http404, HttpResponse

        contract = getattr(self.agent, "contract", None)
        if contract is None or not contract.file:
            raise Http404
        with contract.file.open("rb") as handle:
            data = handle.read()
        response = HttpResponse(data, content_type=contract.content_type)
        response["Content-Disposition"] = f'inline; filename="{contract.filename}"'
        response["Cache-Control"] = "private, no-store"
        return response


class AgentOrSalesManager(IsAgent):
    """An agent or a sales manager: both have a payout account."""

    message = "This area is for partners."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated) and (
            getattr(user, "agent_profile", None) is not None
            or getattr(user, "supervisor_profile", None) is not None
        )


class BankListView(APIView):
    """Nigerian banks Paystack can pay, for the payout account picker.

    Empty when Paystack is not configured; the profile then takes a typed bank
    name as before, and payouts stay with staff.
    """

    permission_classes = (AgentOrSalesManager,)

    def get(self, request):
        from . import paystack_transfers as paystack

        if not paystack.is_configured():
            return Response({"banks": [], "available": False})
        try:
            return Response({"banks": paystack.list_banks(), "available": True})
        except (paystack.PaystackRejected, paystack.PaystackUnreachable):
            return Response({"banks": [], "available": False})


class BankResolveView(APIView):
    """The name on an account, from Paystack, shown before it is saved."""

    permission_classes = (AgentOrSalesManager,)
    throttle_classes = (UserThrottle, MoneyThrottle)

    def post(self, request):
        from . import paystack_transfers as paystack

        code = str(request.data.get("bank_code", "")).strip()
        number = str(request.data.get("account_number", "")).strip()
        if not code or not (number.isdigit() and len(number) == 10):
            return Response({"detail": "Choose your bank and enter the 10-digit account number."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response({"account_name": paystack.resolve_account(number, code)})
        except paystack.PaystackRejected:
            return Response({"detail": "Paystack could not find this account at that bank."}, status=status.HTTP_400_BAD_REQUEST)
        except paystack.PaystackUnreachable:
            return Response({"detail": "The account could not be checked right now. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class SchoolCourseSheetView(AgentScopedMixin, APIView):
    """One partner school's course list as a PDF, for the agent to share.

    The Courses page offers it as a PDF, and as an image the portal draws from
    this same PDF, so both always match.
    """

    def get(self, request, slug):
        from django.http import Http404, HttpResponse

        from apps.catalog.course_sheet import course_sheet_pdf
        from apps.catalog.models import Institution

        institution = (
            Institution.objects.filter(slug=slug, is_active=True).select_related("country").first()
        )
        if institution is None:
            raise Http404
        response = HttpResponse(course_sheet_pdf(institution), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{institution.slug}-courses.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class AgentLettersView(AgentScopedMixin, APIView):
    """Every letter issued to any of this agent's students, newest first."""

    def get(self, request):
        from apps.applications.models import Letter

        letters = (
            Letter.objects.filter(application__submitted_by_agent=self.agent, is_published=True)
            .exclude(file="")
            .select_related("application", "application__institution", "application__destination_country")
            .order_by("-issued_at", "-created_at")
        )
        return Response(
            [
                {
                    "id": letter.id,
                    "title": letter.title,
                    "kind": letter.get_kind_display(),
                    # Relative, so the portal fetches it through its own origin.
                    "url": letter.file.url,
                    "issued_at": letter.issued_at,
                    "reference": letter.application.reference,
                    "student": letter.application.full_name,
                    "university": letter.application.institution.name if letter.application.institution else "",
                    "destination": letter.application.destination_country.name
                    if letter.application.destination_country
                    else "",
                    "sent_to_visa_support": letter.application.transferred_to_visa_support,
                    "visa_status": letter.application.visa_status,
                }
                for letter in letters
            ]
        )


class StudentDraftViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    """Registrations an agent saved to finish later.

    ``files`` adds or replaces one document on a draft; ``files/<id>`` removes it.
    """

    serializer_class = StudentDraftSerializer
    pagination_class = None
    http_method_names = ("get", "post", "put", "patch", "delete", "head", "options")

    def get_queryset(self):
        return StudentDraft.objects.filter(agent=self.agent).prefetch_related("files")

    def perform_create(self, serializer):
        serializer.save(agent=self.agent)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=(MultiPartParser, FormParser),
        throttle_classes=(UserThrottle, UploadThrottle),
    )
    def files(self, request, pk=None):
        from django.conf import settings

        from apps.applications.uploads import validate_upload

        draft = self.get_object()
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
        item = draft.files.filter(slot=slot).first()
        if item is None:
            # A new slot is a new file; replacing one in place is always allowed.
            from apps.applications.uploads import MAX_FILES_PER_DRAFT, check_room

            check_room(draft.files.count(), MAX_FILES_PER_DRAFT)
            item = StudentDraftFile(draft=draft, slot=slot)
        item.kind = kind if kind in {"passport", "academic", "cv", "other"} else "other"
        item.name = name
        item.file = upload
        item.original_filename = upload.name
        item.save()
        draft.save(update_fields=["updated_at"])
        return Response(StudentDraftFileSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"files/(?P<file_id>[0-9]+)")
    def remove_file(self, request, pk=None, file_id=None):
        draft = self.get_object()
        deleted, _ = draft.files.filter(pk=file_id).delete()
        if not deleted:
            return Response({"detail": "No such file on this draft."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommissionListView(AgentScopedMixin, APIView):
    def get(self, request):
        commissions = Commission.objects.filter(agent=self.agent).select_related(
            "application"
        )
        return Response(CommissionSerializer(commissions, many=True).data)


class AgentOverviewView(AgentScopedMixin, APIView):
    """Everything the overview page needs, in one round trip."""

    def get(self, request):
        agent = self.agent
        applications = list(
            Application.objects.filter(submitted_by_agent=agent).select_related(
                "institution", "destination_country"
            )
        )

        admitted_ids = services.admitted_application_ids(a.pk for a in applications)

        def is_admitted(application):
            return application.pk in admitted_ids

        admitted = [a for a in applications if is_admitted(a)]

        # Each student sits in exactly one stage, the furthest they have reached,
        # so the pipeline adds up to the number of students and no stage can go
        # negative. The old version subtracted one count from another and showed
        # "-1 admitted" for a student whose visa was confirmed before admission
        # was recorded.
        pipeline = {"in_review": 0, "admitted": 0, "visa_in_progress": 0, "visa_verified": 0}
        for a in applications:
            if a.visa_status == Application.VisaStatus.COMPLETED:
                pipeline["visa_verified"] += 1
            elif is_admitted(a) and a.visa_status == Application.VisaStatus.IN_PROGRESS:
                pipeline["visa_in_progress"] += 1
            elif is_admitted(a):
                pipeline["admitted"] += 1
            elif a.status in (Application.Status.SUBMITTED, Application.Status.IN_REVIEW):
                pipeline["in_review"] += 1

        wallet = agent.wallet
        wallet.sync_currency()
        from .currency import from_naira

        per_student, _ = from_naira(
            AGENT_REGISTRATION_COMMISSION_NGN + AGENT_VISA_COMMISSION_NGN, wallet.currency
        )
        outstanding = max(
            Decimal("0.00"),
            len(applications) * per_student
            - wallet.registration_commission_total
            - wallet.visa_commission_total,
        )

        recent = (
            Application.objects.filter(submitted_by_agent=agent)
            .select_related("institution", "destination_country", "origin_country", "payment", "fee_parent__payment")
            .prefetch_related("programs", "documents", "commissions", "letters")
            .order_by("-submitted_at")[:5]
        )

        recent_commissions = (
            Commission.objects.filter(agent=agent)
            .select_related("application")
            .order_by("-earned_at")[:10]
        )

        return Response(
            {
                "stats": {
                    "students": len(applications),
                    "admitted": len(admitted),
                    "in_review": pipeline["in_review"],
                },
                "wallet": WalletSerializer(wallet).data,
                "pipeline": pipeline,
                "earnings": {
                    "registration": wallet.registration_commission_total,
                    "visa": wallet.visa_commission_total,
                    "outstanding": outstanding,
                },
                "recent_students": AgentStudentSerializer(recent, many=True).data,
                "recent_commissions": CommissionSerializer(recent_commissions, many=True).data,
                "activity": self._activity(agent, applications),
            }
        )

    def _activity(self, agent, applications):
        events = []
        for app in applications:
            events.append(
                {
                    "at": app.submitted_at,
                    "text": f"{app.full_name} registered for "
                    f"{app.institution.name if app.institution else 'a partner institution'}.",
                }
            )
        for loan in agent.loans.all():
            events.append(
                {
                    "at": loan.requested_at,
                    "text": f"Ads funding of {money(loan.requested_amount, loan.currency)} "
                    f"requested for {loan.purpose}.",
                }
            )
        for wd in agent.withdrawals.all():
            events.append(
                {
                    "at": wd.created_at,
                    "text": f"Withdrawal of {money(wd.amount_requested, wd.currency)} submitted.",
                }
            )
        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:6]
