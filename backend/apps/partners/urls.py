from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BankListView,
    BankResolveView,
    AgentContractFileView,
    AgentContractPreviewView,
    AgentContractSignView,
    AgentContractView,
    AgentCertificateView,
    AgentOverviewView,
    AgentProfileView,
    AgentLettersView,
    AgentStudentViewSet,
    CommissionListView,
    LoanViewSet,
    SavingsView,
    StudentDraftViewSet,
    WalletHistoryView,
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
    path("wallet/history/", WalletHistoryView.as_view(), name="agent-wallet-history"),
    path("commissions/", CommissionListView.as_view(), name="agent-commissions"),
    path("letters/", AgentLettersView.as_view(), name="agent-letters"),
    path("banks/", BankListView.as_view(), name="agent-banks"),
    path("banks/resolve/", BankResolveView.as_view(), name="agent-bank-resolve"),
    path("certificate/", AgentCertificateView.as_view(), name="agent-certificate"),
    path("contract/", AgentContractView.as_view(), name="agent-contract"),
    path("contract/preview/", AgentContractPreviewView.as_view(), name="agent-contract-preview"),
    path("contract/sign/", AgentContractSignView.as_view(), name="agent-contract-sign"),
    path("contract/file/", AgentContractFileView.as_view(), name="agent-contract-file"),
    path("", include(router.urls)),
]
