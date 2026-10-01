import os
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def auto_ensure_admin(sender, **kwargs):
    """Make sure the desk's superuser from the environment exists.

    Runs after every migrate, which also happens at every start-up. It used to
    set the password every time, and a new password hash signs the account out
    of every session, so the desk was logged out whenever a worker restarted.
    The password is now only written when it differs from the one in the
    environment, which still lets DJANGO_ADMIN_PASSWORD reset it.
    """
    email = (os.environ.get("DJANGO_ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("DJANGO_ADMIN_PASSWORD") or ""
    if email and password and sender.name == "apps.accounts":
        from apps.accounts.models import User

        name = os.environ.get("DJANGO_ADMIN_NAME", "Admissions Desk")
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"full_name": name, "role": User.Role.STAFF},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = User.Role.STAFF
        fields = ["is_staff", "is_superuser", "is_active", "role"]
        if not user.check_password(password):
            user.set_password(password)
            fields.append("password")
        user.save(update_fields=fields)


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        # Importing the module is what registers the checks.
        from . import checks  # noqa: F401
        post_migrate.connect(auto_ensure_admin, sender=self)
