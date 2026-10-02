import logging
import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def clean_env_secret(value):
    """A value pasted into a hosting dashboard, without what the paste added.

    Dashboards keep a trailing space or newline from the clipboard, and some
    people wrap the value in quotes as they would in a .env file. Neither is
    part of the password the person means to type, yet the stored password then
    never matched what they typed. Returns the cleaned value and whether
    anything was removed.
    """
    original = value or ""
    cleaned = original.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()
    return cleaned, cleaned != original


def auto_ensure_admin(sender, **kwargs):
    """Make sure the desk's superuser from the environment exists.

    Runs after every migrate, which also happens at every start-up. It used to
    set the password every time, and a new password hash signs the account out
    of every session, so the desk was logged out whenever a worker restarted.
    The password is now only written when it differs from the one in the
    environment, which still lets DJANGO_ADMIN_PASSWORD reset it.
    """
    email = (os.environ.get("DJANGO_ADMIN_EMAIL") or "").strip().lower()
    password, cleaned = clean_env_secret(os.environ.get("DJANGO_ADMIN_PASSWORD"))
    if email and password and sender.name == "apps.accounts":
        from apps.accounts.models import User

        name = os.environ.get("DJANGO_ADMIN_NAME", "Admissions Desk")
        # An account that already has this address, in any capital letters,
        # is the desk's: it is updated, not duplicated. A second row with a
        # different-case address left two accounts, one of which kept the old
        # password.
        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        created = user is None
        if created:
            user = User.objects.create(email=email, full_name=name, role=User.Role.STAFF)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = User.Role.STAFF
        fields = ["email", "is_staff", "is_superuser", "is_active", "role"]
        password_changed = created or not user.check_password(password)
        if password_changed:
            user.set_password(password)
            fields.append("password")
        user.save(update_fields=fields)
        # One line in the host's log, so the address the desk signs in with can
        # be read off instead of guessed. The password is never written.
        logger = logging.getLogger(__name__)
        logger.warning(
            "Admin account %s is ready (%s).",
            email,
            "created" if created else "password updated" if password_changed else "unchanged",
        )
        if cleaned:
            logger.warning(
                "DJANGO_ADMIN_PASSWORD had spaces or quote marks around it; they were "
                "removed. Sign in with the password itself, without them."
            )


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        # Importing the module is what registers the checks.
        from . import checks  # noqa: F401
        post_migrate.connect(auto_ensure_admin, sender=self)
