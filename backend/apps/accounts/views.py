from django.core.cache import cache
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from config.throttles import AnonThrottle, EdgeThrottle, ScopedThrottle

from .cookies import clear_refresh_cookie, read_refresh_token, set_refresh_cookie
from .models import User
from .sessions import stamp, token_matches
from .serializers import (
    AgentRegistrationSerializer,
    ApplicantRegistrationSerializer,
    GabstepTokenObtainPairSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SupportTicketSerializer,
    UserSerializer,
)


def issue_session(user, request=None):
    """A new pair of tokens for this user.

    The refresh token is returned separately from the body so the caller can put
    it in the httpOnly cookie rather than handing it to page scripts.
    """
    refresh = stamp(RefreshToken.for_user(user), user)
    context = {"request": request} if request else {}
    body = {"access": str(refresh.access_token), "user": UserSerializer(user, context=context).data}
    return body, str(refresh)


def session_response(user, request=None, status_code=status.HTTP_200_OK):
    body, refresh = issue_session(user, request=request)
    return set_refresh_cookie(Response(body, status=status_code), refresh)


class LoginThrottle(AnonThrottle):
    """Sign-in attempts, counted per client address.

    Without this the endpoint answers "is this the password?" as fast as anyone
    can ask, which is the whole of a credential-stuffing run. The limit is set
    where a person mistyping their own password never reaches it.
    """

    scope = "login"


class RegistrationThrottle(AnonThrottle):
    scope = "register"


class EmailCheckThrottle(AnonThrottle):
    scope = "email_check"


class SessionThrottle(AnonThrottle):
    """Refreshing is normal and frequent, so this only stops a runaway loop."""

    scope = "user"


class LoginView(TokenObtainPairView):
    """Sign in. The refresh token leaves in a cookie, not in the body."""

    serializer_class = GabstepTokenObtainPairSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (LoginThrottle, EdgeThrottle)

    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 15 * 60

    def post(self, request, *args, **kwargs):
        """Sign in, with a plain answer when it fails and a lock on guessing.

        Wrong email and wrong password get the same message, so the form never
        says which addresses have accounts. Five wrong passwords for one address
        lock that address for 15 minutes, on top of the per-client rate limit,
        so a password cannot be guessed from many machines at once.
        """
        from django.core.cache import cache
        from rest_framework.exceptions import AuthenticationFailed

        email = str(request.data.get("email", "")).strip().lower()
        if not email or not request.data.get("password"):
            return Response(
                {"detail": "Enter your email and password.", "code": "missing_credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key = f"login-failures:{email}"
        if (cache.get(key) or 0) >= self.MAX_FAILURES:
            return Response(
                {
                    "detail": "Too many failed attempts. Wait 15 minutes, or reset your password.",
                    "code": "locked",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Addresses are stored in lower case, so "Ada@Example.com" signs in too.
        serializer = self.get_serializer(
            data={"email": email, "password": request.data.get("password")}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            if cache.add(key, 1, self.LOCKOUT_SECONDS) is False:
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, self.LOCKOUT_SECONDS)
            return Response(
                {"detail": "Invalid email or password.", "code": "invalid_credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        cache.delete(key)
        return session_response(serializer.user, request=request)


class SessionRefreshView(APIView):
    """Trade the refresh cookie for a new access token.

    Reading the token from the cookie is the point: the page never holds it, so a
    script on the page cannot take it. The refresh is rotated on every use, which
    means a stolen one is good for a single call.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (SessionThrottle, EdgeThrottle)

    def post(self, request):
        raw = read_refresh_token(request)
        if not raw:
            return Response(
                {"detail": "No session."}, status=status.HTTP_401_UNAUTHORIZED
            )

        rotated_just_now = False
        try:
            try:
                # Checks the signature, expiry and that it has not been revoked.
                token = RefreshToken(raw)
            except TokenError:
                token = _recently_rotated(raw)
                if token is None:
                    raise
                rotated_just_now = True
            user = User.objects.get(pk=token["user_id"], is_active=True)
            # A session from before a password change is over.
            if not token_matches(token, user):
                raise InvalidToken("Password changed.")
        except (TokenError, InvalidToken, KeyError, User.DoesNotExist):
            # Clear the cookie on the way out so a dead session stops being
            # retried on every page load.
            return clear_refresh_cookie(
                Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
            )

        if not rotated_just_now:
            # Swapped for a new one, so this one is retired, after a short grace
            # for another tab asking at the same moment.
            cache.set(_rotation_key(token), True, ROTATION_GRACE_SECONDS)
            _revoke(token)
        return session_response(user, request=request)


class LogoutView(APIView):
    """End the session: revoke the refresh token, then take the cookie back.

    Deleting the cookie alone left the token itself valid for its full week, so
    a copy taken from the browser kept working after the person signed out.
    """

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        token = _signed_refresh(read_refresh_token(request))
        if token is not None:
            _forget_rotation(token)
            _revoke(token)
        return clear_refresh_cookie(Response(status=status.HTTP_204_NO_CONTENT))


# ── Revoking refresh tokens ──────────────────────────────────────────
#
# Each refresh swaps the cookie's token for a new one and revokes the old, and
# signing out revokes the current one, so a stolen copy stops working.
#
# Two tabs of the same site share one cookie, and both can ask for a refresh at
# the same moment with the same token. The second would then present a token
# the first had just revoked, be refused, and the 401 would clear the cookie
# the first had just been given, signing the person out everywhere. So a token
# revoked by a refresh (not by signing out) is still honoured for a short grace
# period after it was swapped.

ROTATION_GRACE_SECONDS = 60


def _rotation_key(token):
    return f"jwt-rotated:{token['jti']}"


def _signed_refresh(raw):
    """A refresh token whose signature and expiry check out, or None.
    Whether it has been revoked is not looked at here."""
    if not raw:
        return None
    try:
        token = RefreshToken(raw, verify=False)
        token.token_backend.decode(raw, verify=True)  # signature and expiry
        if token.get("token_type") != "refresh" or "jti" not in token:
            return None
        return token
    except (TokenError, InvalidToken, KeyError):
        return None
    except Exception:  # noqa: BLE001 - a malformed token is simply not a session
        return None


def _revoke(token):
    try:
        token.blacklist()
    except Exception:  # noqa: BLE001 - revoking is best effort; the cookie still goes
        pass


def _forget_rotation(token):
    cache.delete(_rotation_key(token))


def _recently_rotated(raw):
    """The token, if it was revoked by a refresh within the grace period."""
    token = _signed_refresh(raw)
    if token is not None and cache.get(_rotation_key(token)):
        return token
    return None


class ApplicantRegisterView(generics.CreateAPIView):
    serializer_class = ApplicantRegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegistrationThrottle, EdgeThrottle)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return verification_pending(user, request=request)


class AgentRegisterView(generics.CreateAPIView):
    serializer_class = AgentRegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegistrationThrottle, EdgeThrottle)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return verification_pending(user, request=request)


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
        user = serializer.save()
        # Changing the password signs out every other device (see sessions.py).
        # This one gets a fresh session so the person making the change stays in.
        response = session_response(user, request=request)
        response.data["detail"] = "Password changed."
        return response


class EmailAvailabilityView(APIView):
    """Whether an address can still be registered.

    This answers a question about someone else's account, so it is the tightest
    limit on the API: asked in a loop it would enumerate every address that holds
    an account here.
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (EmailCheckThrottle, EdgeThrottle)

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
    throttle_classes = (ScopedThrottle, EdgeThrottle)
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


class PasswordResetThrottle(AnonThrottle):
    scope = "password_reset"


class PasswordResetConfirmThrottle(AnonThrottle):
    scope = "password_reset_confirm"


class PasswordResetRequestView(APIView):
    """Email a reset link to an account, without saying whether it exists.

    The answer is identical for a known address, an unknown one, and an address
    that asked a moment ago, so the endpoint cannot be used to find out who has
    an account. The email is sent off the request thread for the same reason:
    the response takes as long either way.

    Accounts with no usable password are skipped. Those are the students an
    agent registered: nobody is given a login for them, and a reset link would
    be one.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (PasswordResetThrottle, EdgeThrottle)
    COOLDOWN_SECONDS = 120

    def post(self, request):
        from django.conf import settings
        from django.contrib.auth.tokens import default_token_generator
        from django.core.cache import cache
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from .emails import _url, send_password_reset_email

        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        cooldown_key = f"password-reset:{email}"
        if (
            user is not None
            and user.has_usable_password()
            and cache.add(cooldown_key, 1, self.COOLDOWN_SECONDS)
        ):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = _url(f"/reset-password?uid={uid}&token={token}")
            minutes = max(1, settings.PASSWORD_RESET_TIMEOUT // 60)
            send_password_reset_email(user, link, minutes)

        return Response(
            {
                "detail": "If an account uses that address, a reset link is on its way. "
                "It expires in one hour."
            }
        )


class PasswordResetValidateView(APIView):
    """Check a reset link before showing the new-password form."""

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (PasswordResetConfirmThrottle, EdgeThrottle)

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data={"uid": request.data.get("uid", ""), "token": request.data.get("token", "")}
        )
        serializer.is_valid(raise_exception=True)
        return Response({"valid": True})


class PasswordResetConfirmView(APIView):
    """Set a new password from a reset link.

    The link stops working the moment it is used, because the token is derived
    from the old password. Every device signed in with the old password is
    signed out, and the owner is told by email that the password changed.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (PasswordResetConfirmThrottle, EdgeThrottle)

    def post(self, request):
        from .emails import send_password_changed_email

        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get("new_password"):
            return Response(
                {"new_password": ["Choose a new password."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        send_password_changed_email(user)
        return Response({"detail": "Your password has been changed.", "role": user.role})


def verification_pending(user, request=None):
    """What a sign-up answers.

    Normally: no session yet, just where the confirmation link went. If the
    link could not be sent, the account is opened anyway and the person is
    signed in, so a mail outage never locks anyone out.
    """
    from .verification import send_or_waive

    if not send_or_waive(user):
        response = session_response(user, request=request, status_code=status.HTTP_201_CREATED)
        response.data["verification_required"] = False
        return response
    return Response(
        {
            "detail": "Check your email to confirm your address.",
            "email": user.email,
            "verification_required": True,
        },
        status=status.HTTP_201_CREATED,
    )


class VerifyEmailThrottle(AnonThrottle):
    scope = "verify"


class VerifyResendThrottle(AnonThrottle):
    scope = "verify_resend"


class VerifyEmailView(APIView):
    """Open a verification link: confirm the address, sign in, send the welcome.

    Opening the same link twice is harmless: the second time it simply signs in
    again, and the welcome email is only ever sent once.
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (VerifyEmailThrottle, EdgeThrottle)

    def post(self, request):
        from .emails import send_welcome_email
        from .verification import user_from_token

        user = user_from_token(request.data.get("token"))
        if user is None:
            return Response(
                {"detail": "This link is invalid or has expired.", "code": "invalid_link"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
            send_welcome_email(user)
        response = session_response(user, request=request)
        response.data["verified"] = True
        return response


class ResendVerificationView(APIView):
    """Send the verification email again. Answers the same for any address."""

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (VerifyResendThrottle, EdgeThrottle)
    COOLDOWN_SECONDS = 60

    def post(self, request):
        from django.core.cache import cache

        from .verification import send_verification

        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if (
            user is not None
            and not user.email_verified
            and cache.add(f"verify-resend:{email}", 1, self.COOLDOWN_SECONDS)
        ):
            send_verification(user)
        return Response(
            {"detail": "If that address is waiting to be confirmed, a new link is on its way."}
        )
