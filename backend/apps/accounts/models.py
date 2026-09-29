"""User accounts.

The platform has two kinds of humans: applicants, who submit one application
for themselves, and partner agents, who submit applications on behalf of many
students and earn commission. Both sign in with an email address, so they share
a single user model and are told apart by ``role``.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.applications.uploads import avatar_upload_path, support_upload_path


class UserManager(BaseUserManager):
    """Manager for a user model keyed on email rather than username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.STAFF)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        APPLICANT = "applicant", _("Applicant")
        AGENT = "agent", _("Partner agent")
        SUPERVISOR = "supervisor", _("Sales manager")
        STAFF = "staff", _("Admissions staff")

    username = None
    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.APPLICANT)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    country = models.CharField(max_length=80, blank=True)
    # False only for someone who signed up themselves and has not yet opened the
    # link in their verification email. See apps/accounts/verification.py.
    email_verified = models.BooleanField(
        default=True,
        help_text="Whether the person has confirmed this email address.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ("-date_joined",)

    def __str__(self):
        return f"{self.full_name or self.email} ({self.role})"

    @property
    def first_name_only(self):
        return (self.full_name or self.email).split(" ")[0]

    @property
    def initials(self):
        parts = [p for p in (self.full_name or "").split(" ") if p]
        return "".join(p[0].upper() for p in parts[:2]) or self.email[:2].upper()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


def _ticket_reference():
    import secrets

    return "SUP-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


class SupportTicket(models.Model):
    """A message someone sent from the Support page in their portal.

    It is emailed to the support inbox as it arrives, with the sender as the
    reply-to address, so the desk answers from its own mailbox. The row is the
    record of it: what was asked, by whom, and whether it has been dealt with.
    """

    class Topic(models.TextChoices):
        APPLICATION = "application", _("My application")
        PAYMENT = "payment", _("Payment")
        DOCUMENTS = "documents", _("Documents and letters")
        ACCOUNT = "account", _("Account and sign-in")
        TECHNICAL = "technical", _("Something is not working")
        OTHER = "other", _("Something else")

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        RESOLVED = "resolved", _("Resolved")

    reference = models.CharField(max_length=12, unique=True, default=_ticket_reference, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="support_tickets"
    )
    topic = models.CharField(max_length=16, choices=Topic.choices, default=Topic.OTHER)
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=5000)
    attachment = models.FileField(upload_to=support_upload_path, blank=True, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    emailed = models.BooleanField(
        default=False, help_text="Whether the message reached the support inbox."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "support message"
        verbose_name_plural = "support messages"

    def __str__(self):
        return f"{self.reference} · {self.subject}"


class SupportReply(models.Model):
    """A reply the desk wrote to a support message, from the admin.

    It is emailed to the person who asked, and shown under their message on the
    Support page, so the answer reaches them even if the email does not.
    """

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField(max_length=5000)
    emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = "reply"
        verbose_name_plural = "replies"

    def __str__(self):
        return f"Reply to {self.ticket.reference}"
