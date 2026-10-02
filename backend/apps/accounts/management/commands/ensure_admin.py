"""Create or reset the admissions-desk superuser without a prompt.

`createsuperuser` is interactive, which is awkward in a setup script or a
container. This does the same job from flags or environment variables and is safe
to run repeatedly: an existing account keeps its data and simply has its password
and staff flags reset.

There is no default password. There used to be, it was written in the README, and
a fixed literal in a public file is the whole attack: anyone who found the admin
URL already had the credentials to the desk that approves visas and releases
money. A password must be supplied, or the command generates one and prints it
once.
"""

import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils.crypto import get_random_string

from apps.accounts.apps import clean_env_secret
from apps.accounts.models import User

# Unambiguous when read aloud or copied off a terminal: no O/0, no l/1.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


class Command(BaseCommand):
    help = "Create or update the admin superuser non-interactively."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_ADMIN_EMAIL", ""),
            help="Defaults to DJANGO_ADMIN_EMAIL.",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_ADMIN_PASSWORD", ""),
            help="Defaults to DJANGO_ADMIN_PASSWORD. Generated if neither is given.",
        )
        parser.add_argument(
            "--name",
            default=os.environ.get("DJANGO_ADMIN_NAME", "Admissions Desk"),
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        if not email:
            raise CommandError(
                "An email address is required. Pass --email or set DJANGO_ADMIN_EMAIL."
            )

        password, _ = clean_env_secret(options["password"])
        generated = False
        if not password:
            password = get_random_string(20, ALPHABET)
            generated = True

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("That password was rejected: " + " ".join(exc.messages))

        # An existing account with this address, in any capital letters, is
        # updated rather than duplicated.
        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        created = user is None
        if created:
            user = User.objects.create(email=email, full_name=options["name"], role=User.Role.STAFF)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = User.Role.STAFF
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f"Admin {'created' if created else 'updated'}: {email}")
        )
        if generated:
            # Printed once, on purpose. It is not stored anywhere in readable form
            # and cannot be recovered: run the command again to set a new one.
            self.stdout.write(
                self.style.WARNING(
                    f"  Generated password: {password}\n"
                    "  Save it now. It is not shown again and is not recoverable."
                )
            )
        else:
            self.stdout.write("  Password set from the value you supplied.")
        self.stdout.write("  Sign in at /admin/")
