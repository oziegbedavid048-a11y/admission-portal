"""User accounts.

The platform has two kinds of humans: applicants, who submit one application
for themselves, and partner agents, who submit applications on behalf of many
students and earn commission. Both sign in with an email address, so they share
a single user model and are told apart by ``role``.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


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
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    country = models.CharField(max_length=80, blank=True)

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
