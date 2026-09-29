from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .cookies import clear_refresh_cookie, read_refresh_token, set_refresh_cookie
from .models import User
from .serializers import (
    AgentRegistrationSerializer,
    ApplicantRegistrationSerializer,
    GabstepTokenObtainPairSerializer,
    PasswordChangeSerializer,
    SupportTicketSerializer,
    UserSerializer,
)


def issue_session(user, request=None):
    """A new pair of tokens for this user.

    The refresh token is returned separately from the body so the caller can put
    it in the httpOnly cookie rather than handing it to page scripts.
    """
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["full_name"] = user.full_name
    context = {"request": request} if request else {}
    body = {"access": str(refresh.access_token), "user": UserSerializer(user, context=context).data}
    return body, str(refresh)


def session_response(user, request=None, status_code=status.HTTP_200_OK):
    body, refresh = issue_session(user, request=request)
    return set_refresh_cookie(Response(body, status=status_code), refresh)


class LoginThrottle(AnonRateThrottle):
    """Sign-in attempts, counted per client address.

    Without this the endpoint answers "is this the password?" as fast as anyone
    can ask, which is the whole of a credential-stuffing run. The limit is set
    where a person mistyping their own password never reaches it.
    """

    scope = "login"


class RegistrationThrottle(AnonRateThrottle):
    scope = "register"


class EmailCheckThrottle(AnonRateThrottle):
    scope = "email_check"


class SessionThrottle(AnonRateThrottle):
    """Refreshing is normal and frequent, so this only stops a runaway loop."""

    scope = "user"


class LoginView(TokenObtainPairView):
    """Sign in. The refresh token leaves in a cookie, not in the body."""

    serializer_class = GabstepTokenObtainPairSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (LoginThrottle,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return session_response(serializer.user, request=request)


class SessionRefreshView(APIView):
    """Trade the refresh cookie for a new access token.

    Reading the token from the cookie is the point: the page never holds it, so a
    script on the page cannot take it. The refresh is rotated on every use, which
    means a stolen one is good for a single call.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (SessionThrottle,)

    def post(self, request):
        raw = read_refresh_token(request)
        if not raw:
            return Response(
                {"detail": "No session."}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            token = RefreshToken(raw)
            user = User.objects.get(pk=token["user_id"], is_active=True)
        except (TokenError, InvalidToken, KeyError, User.DoesNotExist):
            # Clear the cookie on the way out so a dead session stops being
            # retried on every page load.
            return clear_refresh_cookie(
                Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
            )

        return session_response(user, request=request)


class LogoutView(APIView):
    """End the session and take the cookie back."""

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        return clear_refresh_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class ApplicantRegisterView(generics.CreateAPIView):
    serializer_class = ApplicantRegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegistrationThrottle,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return session_response(user, request=request, status_code=status.HTTP_201_CREATED)


class AgentRegisterView(generics.CreateAPIView):
    serializer_class = AgentRegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegistrationThrottle,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return session_response(user, request=request, status_code=status.HTTP_201_CREATED)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed."})


class EmailAvailabilityView(APIView):
    """Whether an address can still be registered.

    This answers a question about someone else's account, so it is the tightest
    limit on the API: asked in a loop it would enumerate every address that holds
    an account here.
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (EmailCheckThrottle,)

    def get(self, request):
        email = (request.query_params.get("email") or "").strip().lower()
        taken = bool(email) and User.objects.filter(email__iexact=email).exists()
        return Response({"email": email, "available": not taken})


class SupportTicketView(generics.ListCreateAPIView):
    """The Support page: send the desk a message, and see the ones already sent.

    Creating one emails it to the support inbox straight away, with the sender as
    reply-to. If the mail provider refuses, the message is still kept, and the
    desk sees it in the admin; the response says which happened.
    """

    serializer_class = SupportTicketSerializer
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "support"

    def get_throttles(self):
        # Reading your own messages is free; only sending counts.
        return super().get_throttles() if self.request.method == "POST" else []

    def get_queryset(self):
        return self.request.user.support_tickets.all()[:20]

    def perform_create(self, serializer):
        from .emails import send_support_ticket_email

        ticket = serializer.save(user=self.request.user)
        ticket.emailed = bool(send_support_ticket_email(ticket))
        ticket.save(update_fields=["emailed"])
