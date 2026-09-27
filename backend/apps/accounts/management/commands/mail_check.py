"""Find out whether this host can actually send mail, and say why not.

"No email arrived" has several causes that look identical from the outside: a
wrong password, a mail server that is down, or a host that blocks outbound SMTP
altogether. The last one is the common surprise on a managed platform. Several
block outbound connections on ports 25, 465 and 587 on their cheaper instances,
because that is how spam leaves a network, and there is nothing in the
application to fix when they do: the connection never opens.

This reports each step separately so the answer is unambiguous:

    python manage.py mail_check --to you@example.com
"""

import smtplib
import socket
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test the mail configuration and report exactly where it fails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default=settings.EMAIL_HOST_USER,
            help="Where to send the test. Defaults to the sending mailbox itself.",
        )

    def handle(self, *args, **options):
        w, s, e = self.stdout.write, self.style.SUCCESS, self.style.ERROR
        host, port = settings.EMAIL_HOST, settings.EMAIL_PORT

        w("Configuration")
        w(f"  backend       {settings.EMAIL_BACKEND}")
        w(f"  host          {host}:{port}")
        w(f"  ssl / tls     {settings.EMAIL_USE_SSL} / {settings.EMAIL_USE_TLS}")
        w(f"  user          {settings.EMAIL_HOST_USER}")
        w(f"  password set  {bool(settings.EMAIL_HOST_PASSWORD)}")
        w(f"  from          {settings.DEFAULT_FROM_EMAIL}")
        w("")

        if "smtp" not in settings.EMAIL_BACKEND:
            w(self.style.WARNING("Not using the SMTP backend, so nothing leaves this host."))
            return

        if not settings.EMAIL_HOST_PASSWORD:
            w(e("EMAIL_HOST_PASSWORD is empty. Nothing will send until it is set."))
            return

        # 1. Can a socket even open? This is the step a platform-level block fails.
        w("1. Opening a TCP connection")
        started = time.time()
        try:
            sock = socket.create_connection((host, port), timeout=15)
            sock.close()
            w(s(f"   connected in {time.time() - started:.2f}s"))
        except OSError as exc:
            w(e(f"   failed after {time.time() - started:.2f}s: {exc}"))
            w("")
            w(self.style.WARNING(
                "   A timeout here usually means this host blocks outbound SMTP\n"
                "   rather than anything being wrong with the mail server or the\n"
                "   password. Managed platforms commonly block ports 25, 465 and\n"
                "   587 on their cheaper instances.\n"
                "\n"
                "   Two ways out: move to an instance where outbound SMTP is\n"
                "   allowed, or send through a provider's HTTPS API instead, which\n"
                "   is never blocked because it is ordinary web traffic."
            ))
            return

        # 2. Does the server accept these credentials?
        w("2. Logging in")
        try:
            if settings.EMAIL_USE_SSL:
                server = smtplib.SMTP_SSL(host, port, timeout=20)
            else:
                server = smtplib.SMTP(host, port, timeout=20)
                if settings.EMAIL_USE_TLS:
                    server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.quit()
            w(s("   accepted"))
        except smtplib.SMTPAuthenticationError as exc:
            w(e(f"   rejected the credentials: {exc}"))
            w(self.style.WARNING("   Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."))
            return
        except Exception as exc:
            w(e(f"   {type(exc).__name__}: {exc}"))
            return

        # 3. Does a real message go out?
        w(f"3. Sending a message to {options['to']}")
        try:
            message = EmailMultiAlternatives(
                subject="Gabstep mail check",
                body=(
                    "If you are reading this, this host can send mail.\n\n"
                    f"Sent from {host}:{port} as {settings.EMAIL_HOST_USER}."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[options["to"]],
            )
            message.send(fail_silently=False)
            w(s("   sent"))
            w("")
            w(s("Mail works from this host."))
        except Exception as exc:
            w(e(f"   {type(exc).__name__}: {exc}"))
