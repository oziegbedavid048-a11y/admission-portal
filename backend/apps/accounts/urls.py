from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    AgentRegisterView,
    ApplicantRegisterView,
    EmailAvailabilityView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    ResendVerificationView,
    VerifyEmailView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetValidateView,
    SessionRefreshView,
    SupportTicketView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    # Reads the httpOnly refresh cookie rather than a token in the body, so the
    # page never has to hold one. SimpleJWT's own TokenRefreshView is not used.
    path("refresh/", SessionRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("register/applicant/", ApplicantRegisterView.as_view(), name="register-applicant"),
    path("register/agent/", AgentRegisterView.as_view(), name="register-agent"),
    path("me/", MeView.as_view(), name="me"),
    path("password/", PasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", PasswordResetRequestView.as_view(), name="password-forgot"),
    path("password/reset/validate/", PasswordResetValidateView.as_view(), name="password-reset-validate"),
    path("password/reset/", PasswordResetConfirmView.as_view(), name="password-reset"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("verify-email/resend/", ResendVerificationView.as_view(), name="verify-email-resend"),
    path("email-available/", EmailAvailabilityView.as_view(), name="email-available"),
    path("support/", SupportTicketView.as_view(), name="support"),
]
