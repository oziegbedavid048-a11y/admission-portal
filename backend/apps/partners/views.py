from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.applications import services
from apps.applications.constants import AGENT_COMMISSION_PER_MILESTONE
from apps.applications.models import Application

from .models import Commission, Loan, Withdrawal
from .permissions import IsAgent
from .serializers import (
    AgentProfileSerializer,
    AgentStudentCreateSerializer,
    AgentStudentNoteSerializer,
    AgentStudentSerializer,
    CommissionSerializer,
    LoanSerializer,
    ReleaseFromSavingsSerializer,
    SaveToSavingsSerializer,
    WalletSerializer,
    WithdrawalRequestSerializer,
    WithdrawalSerializer,
)


class AgentScopedMixin:
    permission_classes = (IsAgent,)

    @property
    def agent(self):
        return self.request.user.agent_profile


class MoneyThrottle(ScopedRateThrottle):
    """Anything that moves money, held well below what a person would ever do."""

    scope = "money"


class AgentProfileView(AgentScopedMixin, RetrieveUpdateAPIView):
    serializer_class = AgentProfileSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self):
        return self.agent


class WalletView(AgentScopedMixin, APIView):
    def get(self, request):
        return Response(WalletSerializer(self.agent.wallet).data)


class WithdrawalViewSet(AgentScopedMixin, viewsets.ModelViewSet):
    serializer_class = WithdrawalSerializer
    http_method_names = ("get", "post", "head", "options")
    pagination_class = None

    def get_queryset(self):
        return Withdrawal.objects.filter(agent=self.agent)

    throttle_classes = (MoneyThrottle,)

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

    throttle_classes = (MoneyThrottle,)

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

    throttle_classes = (MoneyThrottle,)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "agent": self.agent}

    def perform_create(self, serializer):
        serializer.save(agent=self.agent)


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
            .select_related("payment")
            .prefetch_related("programs", "documents", "commissions")
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

        admitted = [a for a in applications if a.status == Application.Status.ADMITTED]
        visas = [
            a for a in applications if a.visa_status == Application.VisaStatus.COMPLETED
        ]

        # Each student sits in exactly one stage, the furthest they have reached,
        # so the pipeline adds up to the number of students and no stage can go
        # negative. The old version subtracted one count from another and showed
        # "-1 admitted" for a student whose visa was confirmed before admission
        # was recorded.
        pipeline = {"in_review": 0, "admitted": 0, "visa_in_progress": 0, "visa_verified": 0}
        for a in applications:
            if a.visa_status == Application.VisaStatus.COMPLETED:
                pipeline["visa_verified"] += 1
            elif a.status == Application.Status.ADMITTED and a.visa_status == Application.VisaStatus.IN_PROGRESS:
                pipeline["visa_in_progress"] += 1
            elif a.status == Application.Status.ADMITTED:
                pipeline["admitted"] += 1
            elif a.status in (Application.Status.SUBMITTED, Application.Status.IN_REVIEW):
                pipeline["in_review"] += 1

        wallet = agent.wallet
        outstanding = max(
            Decimal("0.00"),
            len(applications) * AGENT_COMMISSION_PER_MILESTONE * 2
            - wallet.registration_commission_total
            - wallet.visa_commission_total,
        )

        recent = (
            Application.objects.filter(submitted_by_agent=agent)
            .select_related("institution", "destination_country", "origin_country", "payment")
            .prefetch_related("programs", "documents", "commissions")
            .order_by("-submitted_at")[:4]
        )

        recent_commissions = (
            Commission.objects.filter(agent=agent)
            .select_related("application")
            .order_by("-earned_at")[:6]
        )

        return Response(
            {
                "stats": {
                    "students": len(applications),
                    "admitted": len(admitted),
                    "visas_verified": len(visas),
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
                    "text": f"Ad funding of ₦{loan.requested_amount:,.0f} "
                    f"requested for {loan.purpose}.",
                }
            )
        for wd in agent.withdrawals.all():
            events.append(
                {
                    "at": wd.created_at,
                    "text": f"Withdrawal of ₦{wd.amount_requested:,.0f} submitted.",
                }
            )
        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:6]
