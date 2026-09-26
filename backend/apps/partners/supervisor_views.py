"""The sales manager's read-only window onto their team."""

from decimal import Decimal

from django.db.models import Count, Max, Q, Sum
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.constants import SUPERVISOR_BONUS_NGN
from apps.applications.models import Application
from apps.payments.models import Payment

from .models import AgentProfile, SupervisorBonus, SupervisorWithdrawal
from .supervisor_serializers import (
    SupervisedAgentSerializer,
    SupervisedStudentSerializer,
    SupervisorBonusSerializer,
    SupervisorProfileSerializer,
    SupervisorWithdrawalRequestSerializer,
    SupervisorWithdrawalSerializer,
)


class IsSupervisor(BasePermission):
    message = "This area is for sales managers."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "supervisor_profile", None) is not None
        )


class SupervisorScopedMixin:
    permission_classes = (IsSupervisor,)

    @property
    def supervisor(self):
        return self.request.user.supervisor_profile

    def agent_queryset(self):
        """Agents under this sales manager, with their totals counted in SQL.

        Annotating here keeps a table of twenty agents to a single query rather
        than twenty more as each row asks for its own counts.
        """
        return (
            AgentProfile.objects.filter(supervisor=self.supervisor)
            .select_related("user", "wallet")
            .prefetch_related("supervisor_bonuses")
            .annotate(
                student_count=Count("applications", distinct=True),
                paid_count=Count(
                    "applications",
                    filter=Q(applications__payment__status=Payment.Status.PAID),
                    distinct=True,
                ),
                admitted_count=Count(
                    "applications",
                    filter=Q(applications__status=Application.Status.ADMITTED),
                    distinct=True,
                ),
                visa_count=Count(
                    "applications",
                    filter=Q(applications__visa_status=Application.VisaStatus.COMPLETED),
                    distinct=True,
                ),
                last_submission=Max("applications__submitted_at"),
            )
            .order_by("user__full_name")
        )

    def student_queryset(self):
        return (
            Application.objects.filter(submitted_by_agent__supervisor=self.supervisor)
            .select_related(
                "submitted_by_agent__user",
                "institution",
                "destination_country",
                "origin_country",
                "payment",
            )
            .prefetch_related("programs")
            .order_by("-submitted_at")
        )


class SupervisorProfileView(SupervisorScopedMixin, RetrieveUpdateAPIView):
    serializer_class = SupervisorProfileSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self):
        return self.supervisor


class SupervisorAgentViewSet(SupervisorScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = SupervisedAgentSerializer
    pagination_class = None
    search_fields = ("user__full_name", "user__email", "agency_name")

    def get_queryset(self):
        return self.agent_queryset()


class SupervisorStudentViewSet(SupervisorScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = SupervisedStudentSerializer
    lookup_field = "reference"
    pagination_class = None
    search_fields = ("full_name", "reference", "institution__name", "email")
    filterset_fields = ("status", "visa_status")

    def get_queryset(self):
        queryset = self.student_queryset()
        agent = self.request.query_params.get("agent")
        if agent and agent != "all":
            queryset = queryset.filter(submitted_by_agent_id=agent)
        return queryset


class SupervisorBonusListView(SupervisorScopedMixin, APIView):
    def get(self, request):
        bonuses = SupervisorBonus.objects.filter(
            supervisor=self.supervisor
        ).select_related("agent__user", "application", "application__institution")
        return Response(SupervisorBonusSerializer(bonuses, many=True).data)


class SupervisorOverviewView(SupervisorScopedMixin, APIView):
    """Everything the sales manager overview needs, in one round trip."""

    def get(self, request):
        supervisor = self.supervisor
        agents = list(self.agent_queryset())
        students = list(self.student_queryset())

        admitted = [s for s in students if s.status == Application.Status.ADMITTED]
        visas = [
            s for s in students if s.visa_status == Application.VisaStatus.COMPLETED
        ]
        paid = [
            s
            for s in students
            if getattr(s, "payment", None) and s.payment.status == Payment.Status.PAID
        ]

        pipeline = {
            "awaiting_fee": len(students) - len(paid),
            "in_review": sum(
                1
                for s in students
                if s.status
                in (Application.Status.SUBMITTED, Application.Status.IN_REVIEW)
                and getattr(s, "payment", None)
                and s.payment.status == Payment.Status.PAID
            ),
            "admitted": len(admitted) - len(visas),
            "visa_verified": len(visas),
        }

        team_earned = (
            AgentProfile.objects.filter(supervisor=supervisor).aggregate(
                total=Sum("wallet__total_earned")
            )["total"]
            or Decimal("0.00")
        )

        bonus_by_agent = [
            {
                "agent": agent.user.full_name or agent.user.email,
                "amount": sum(
                    (b.amount for b in agent.supervisor_bonuses.all()), Decimal("0.00")
                ),
                "students": agent.student_count,
            }
            for agent in agents
        ]
        bonus_by_agent.sort(key=lambda row: row["amount"], reverse=True)

        return Response(
            {
                "profile": SupervisorProfileSerializer(supervisor).data,
                "stats": {
                    "agents": len(agents),
                    "students": len(students),
                    "admitted": len(admitted),
                    "visas_verified": len(visas),
                    "fees_paid": len(paid),
                },
                "earnings": {
                    "bonus_total": supervisor.bonus_total,
                    "per_student": SUPERVISOR_BONUS_NGN,
                    "team_earned": team_earned,
                    "by_agent": bonus_by_agent,
                },
                "pipeline": pipeline,
                "top_agents": SupervisedAgentSerializer(
                    sorted(agents, key=lambda a: a.student_count, reverse=True)[:5],
                    many=True,
                ).data,
                "recent_students": SupervisedStudentSerializer(students[:6], many=True).data,
                "activity": self._activity(supervisor, students, agents),
            }
        )

    def _activity(self, supervisor, students, agents):
        events = []
        for student in students:
            agent_name = (
                student.submitted_by_agent.user.full_name
                if student.submitted_by_agent
                else "An agent"
            )
            events.append(
                {
                    "at": student.submitted_at,
                    "text": f"{agent_name} registered {student.full_name}.",
                }
            )
        for bonus in supervisor.bonuses.select_related("application")[:20]:
            events.append(
                {
                    "at": bonus.earned_at,
                    "text": f"₦{bonus.amount:,.0f} bonus earned for "
                    f"{bonus.application.full_name}.",
                }
            )
        for agent in agents:
            events.append(
                {
                    "at": agent.created_at,
                    "text": f"{agent.user.full_name} joined your team.",
                }
            )

        events = [e for e in events if e["at"]]
        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:8]


class SupervisorWithdrawalViewSet(SupervisorScopedMixin, viewsets.ModelViewSet):
    """Request a payout of the bonus balance, and see the ones already asked for."""

    serializer_class = SupervisorWithdrawalSerializer
    http_method_names = ("get", "post", "head", "options")
    pagination_class = None

    def get_queryset(self):
        return SupervisorWithdrawal.objects.filter(supervisor=self.supervisor)

    def create(self, request, *args, **kwargs):
        serializer = SupervisorWithdrawalRequestSerializer(
            data=request.data, context={"supervisor": self.supervisor}
        )
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal = SupervisorWithdrawal.request(
                self.supervisor, serializer.validated_data["amount"]
            )
        except DjangoValidationError as exc:
            # Raised inside the row lock, which is the check that actually counts.
            raise drf_serializers.ValidationError({"amount": exc.messages})
        self.supervisor.refresh_from_db()
        return Response(
            {
                "withdrawal": SupervisorWithdrawalSerializer(withdrawal).data,
                "profile": SupervisorProfileSerializer(self.supervisor).data,
            },
            status=status.HTTP_201_CREATED,
        )
