import os
from django.apps import AppConfig
from django.db.models.signals import post_migrate


def auto_ensure_admin(sender, **kwargs):
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
        user.set_password(password)
        user.save()


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        # Importing the module is what registers the checks.
        from . import checks  # noqa: F401
        post_migrate.connect(auto_ensure_admin, sender=self)
