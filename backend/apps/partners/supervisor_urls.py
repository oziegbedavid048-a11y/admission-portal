from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .supervisor_views import (
    SupervisorAgentViewSet,
    SupervisorBonusListView,
    SupervisorOverviewView,
    SupervisorProfileView,
    SupervisorStudentViewSet,
    SupervisorWithdrawalViewSet,
)

router = DefaultRouter()
router.register("agents", SupervisorAgentViewSet, basename="supervisor-agent")
router.register("students", SupervisorStudentViewSet, basename="supervisor-student")
router.register("withdrawals", SupervisorWithdrawalViewSet, basename="supervisor-withdrawal")

urlpatterns = [
    path("me/", SupervisorProfileView.as_view(), name="supervisor-profile"),
    path("overview/", SupervisorOverviewView.as_view(), name="supervisor-overview"),
    path("bonuses/", SupervisorBonusListView.as_view(), name="supervisor-bonuses"),
    path("", include(router.urls)),
]
