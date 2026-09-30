from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentOverviewView,
    AgentProfileView,
    AgentLettersView,
    AgentStudentViewSet,
    CommissionListView,
    LoanViewSet,
    SavingsView,
    StudentDraftViewSet,
    WalletView,
    WithdrawalViewSet,
)

router = DefaultRouter()
router.register("students", AgentStudentViewSet, basename="agent-student")
router.register("drafts", StudentDraftViewSet, basename="agent-draft")
router.register("loans", LoanViewSet, basename="agent-loan")
router.register("withdrawals", WithdrawalViewSet, basename="agent-withdrawal")

urlpatterns = [
    path("me/", AgentProfileView.as_view(), name="agent-profile"),
    path("overview/", AgentOverviewView.as_view(), name="agent-overview"),
    path("wallet/", WalletView.as_view(), name="agent-wallet"),
    path("wallet/savings/", SavingsView.as_view(), name="agent-savings"),
    path("commissions/", CommissionListView.as_view(), name="agent-commissions"),
    path("letters/", AgentLettersView.as_view(), name="agent-letters"),
    path("", include(router.urls)),
]
