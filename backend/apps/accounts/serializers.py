from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.partners.models import AgentProfile, SupervisorProfile, Wallet

from .models import SupportReply, SupportTicket, User


class UserSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)

    def validate_avatar(self, value):
        from django.conf import settings

        from apps.applications.uploads import validate_upload

        # A profile picture is served from the same origin as the portal, so it
        # goes through the same check as a document rather than trusting the
        # field type.
        # Compressed to a small JPEG before it is stored, so a large phone photo
        # is accepted rather than refused.
        return validate_upload(value, settings.MAX_UPLOAD_SIZE_MB)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "country",
            "avatar",
            "initials",
            "date_joined",
        )
        # `email` is the sign-in identity and the address every letter and
        # status update is sent to. Letting someone change it on themselves, with
        # no confirmation to either the old or the new address, means a stolen
        # token can quietly move the account somewhere its owner cannot reach.
        # Changing it is a desk job until there is a verification flow.
        read_only_fields = ("id", "email", "role", "date_joined", "initials")


class ApplicantRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    send_welcome_email = serializers.BooleanField(required=False, default=True, write_only=True)

    class Meta:
        model = User
        fields = ("email", "full_name", "phone", "country", "password", "send_welcome_email")
        extra_kwargs = {
            "full_name": {"required": True, "allow_blank": False},
            "phone": {"required": True, "allow_blank": False},
        }

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_full_name(self, value):
        value = " ".join(value.split())
        if len(value) < 3 or len(value.split(" ")) < 2:
            raise serializers.ValidationError("Enter your first and last name.")
        if len(value) > 180:
            raise serializers.ValidationError("That name is too long.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if not 7 <= len(digits) <= 15 or any(ch not in "+0123456789 ()-" for ch in value):
            raise serializers.ValidationError("Enter a valid phone number, for example +234 801 234 5678.")
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        raw_password = validated_data.get("password")
        send_email = validated_data.pop("send_welcome_email", True)
        user = User.objects.create_user(
            role=User.Role.APPLICANT, email_verified=False, **validated_data
        )
        # The verification email is sent by the view once the account exists.
        return user


class AgentRegistrationSerializer(serializers.Serializer):
    """Creates the agent user, their partner profile and an empty wallet."""

    full_name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40)
    password = serializers.CharField(write_only=True, min_length=8)
    bank_name = serializers.CharField(max_length=120)
    account_number = serializers.RegexField(r"^\d{10}$")
    account_name = serializers.CharField(max_length=120)
    agency_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    country = serializers.CharField(max_length=80, required=False, allow_blank=True)
    agent_code = serializers.CharField(
        max_length=12,
        required=False,
        allow_blank=True,
        help_text="The code from your sales manager, if you were referred by one.",
    )

    def validate_full_name(self, value):
        return ApplicantRegistrationSerializer.validate_full_name(self, value)

    def validate_phone(self, value):
        return ApplicantRegistrationSerializer.validate_phone(self, value)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered. Please sign in.")
        return value.lower()

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate_agent_code(self, value):
        """Resolve the code to the sales manager it belongs to.

        Blank is allowed: an agent can join without one. A code that is given,
        though, has to be real, because a typo would silently leave the agent
        unattached and nobody would notice until a bonus went unpaid.
        """
        code = (value or "").strip().upper()
        if not code:
            return None

        supervisor = SupervisorProfile.objects.filter(
            agent_code__iexact=code, is_active=True
        ).first()
        if supervisor is None:
            raise serializers.ValidationError(
                "That agent code does not match an active sales manager. "
                "Check it with them, or leave it blank."
            )
        return supervisor

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email_verified=False,
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            phone=validated_data["phone"],
            country=validated_data.get("country", "") or "Nigeria",
            role=User.Role.AGENT,
        )
        profile = AgentProfile.objects.create(
            user=user,
            bank_name=validated_data["bank_name"],
            account_number=validated_data["account_number"],
            account_name=validated_data["account_name"],
            agency_name=validated_data.get("agency_name", ""),
            supervisor=validated_data.get("agent_code"),
        )
        Wallet.objects.create(agent=profile)
        # The verification email is sent by the view once the account exists.
        return user


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("That is not your current password.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


def _still_waiting(user):
    """Whether an unconfirmed account must keep waiting for its link.

    Signing in resends the link (at most once a minute). If the mail provider
    refuses it, the account is opened rather than left locked; see
    verification.send_or_waive.
    """
    from django.core.cache import cache

    from .verification import send_or_waive

    if not cache.add(f"verify-on-login:{user.pk}", 1, 60):
        return True
    return send_or_waive(user)


class GabstepTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the role to the token payload and the user object to the response."""

    @classmethod
    def get_token(cls, user):
        from .sessions import stamp

        return stamp(super().get_token(user), user)

    def validate(self, attrs):
        from rest_framework.exceptions import PermissionDenied

        data = super().validate(attrs)
        # Checked after the password, so this never tells a stranger whether an
        # address is registered.
        if not self.user.email_verified and _still_waiting(self.user):
            raise PermissionDenied(
                {
                    "detail": "Confirm your email address first. We sent you a link when you signed up.",
                    "code": "email_not_verified",
                }
            )
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class SupportReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportReply
        fields = ("id", "body", "created_at")
        read_only_fields = fields


class SupportTicketSerializer(serializers.ModelSerializer):
    """A message from the Support page. The sender is whoever is signed in."""

    topic_display = serializers.CharField(source="get_topic_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    replies = SupportReplySerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = (
            "reference",
            "topic",
            "topic_display",
            "subject",
            "message",
            "attachment",
            "status",
            "status_display",
            "emailed",
            "created_at",
            "replies",
        )
        read_only_fields = ("reference", "status", "emailed", "created_at", "replies")

    def validate_subject(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Add a short subject.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Tell us a little more, so we can help.")
        return value

    def validate_attachment(self, value):
        from django.conf import settings

        from apps.applications.uploads import validate_upload

        return validate_upload(value, settings.MAX_UPLOAD_SIZE_MB)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """A reset link's uid and token, and the new password.

    Invalid and expired links get the same answer, so the response says nothing
    about which accounts exist.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, required=False)

    LINK_ERROR = "This reset link is invalid or has expired. Ask for a new one."

    def validate(self, attrs):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": self.LINK_ERROR})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": self.LINK_ERROR})

        password = attrs.get("new_password")
        if password is not None:
            try:
                password_validation.validate_password(password, user)
            except Exception as exc:  # Django's ValidationError, reshaped for DRF
                raise serializers.ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))})
        attrs["user"] = user
        return attrs
