from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.partners.models import AgentProfile, SupervisorProfile, Wallet

from .models import SupportTicket, User


class UserSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)

    def validate_avatar(self, value):
        from django.conf import settings

        from apps.applications.uploads import validate_upload

        # A profile picture is served from the same origin as the portal, so it
        # goes through the same check as a document rather than trusting the
        # field type.
        return validate_upload(value, min(settings.MAX_UPLOAD_SIZE_MB, 5))

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

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        raw_password = validated_data.get("password")
        send_email = validated_data.pop("send_welcome_email", True)
        user = User.objects.create_user(role=User.Role.APPLICANT, **validated_data)
        if send_email:
            try:
                from .emails import send_applicant_welcome_email
                # They chose this password themselves, so it is never sent back
                # to them: the email only confirms the account exists.
                send_applicant_welcome_email(user)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("Failed to send applicant welcome email: %s", exc)
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
        try:
            from .emails import send_agent_welcome_email
            send_agent_welcome_email(user, agent_profile=profile)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Failed to send agent welcome email: %s", exc)
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


class GabstepTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the role to the token payload and the user object to the response."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class SupportTicketSerializer(serializers.ModelSerializer):
    """A message from the Support page. The sender is whoever is signed in."""

    topic_display = serializers.CharField(source="get_topic_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

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
        )
        read_only_fields = ("reference", "status", "emailed", "created_at")

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
        from apps.applications.uploads import validate_upload

        return validate_upload(value, 5)
