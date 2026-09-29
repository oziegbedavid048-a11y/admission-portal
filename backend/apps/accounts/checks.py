"""Deployment checks that catch settings which are fine locally and wrong live.

These run with every `manage.py` command and with `manage.py check --deploy`, so
a misconfiguration is caught before it sends anybody an email or serves anybody a
page rather than after.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}

# Warnings rather than errors below, deliberately. A wrong FRONTEND_URL was
# already live when these checks were written, and the host auto-deploys on push,
# so raising would have turned a bad setting into an outage the moment this
# shipped. The point is to name the problem on every boot, not to stop the boot.

# Hosting dashboards. Their URLs look plausible enough to paste into a settings
# field, and a deployment dashboard is never where a visitor should be sent. This
# is not a guess: FRONTEND_URL was once set to
# https://vercel.com/<team>/<project>/<deployment-id>, which sent every applicant
# returning from the payment provider to a Vercel 404, and pointed every link in
# every email at the same place.
DASHBOARD_HOSTS = {
    "vercel.com",
    "dashboard.render.com",
    "render.com",
    "app.netlify.com",
    "github.com",
    "console.cloud.google.com",
    "portal.azure.com",
}


@register()
def check_frontend_url(app_configs, **kwargs):
    """Every link in every email is built from FRONTEND_URL.

    Left at its development default on a live deployment, every "Sign in" and
    "View your application" button in every message points at a machine only the
    developer has. The mail still sends, so nothing fails loudly: the recipient
    just gets a link that cannot work. That is worth refusing to start over.
    """
    issues = []
    url = getattr(settings, "FRONTEND_URL", "") or ""
    host = (urlparse(url).hostname or "").lower()

    if settings.DEBUG:
        return issues

    if not url:
        issues.append(
            Error(
                "FRONTEND_URL is empty, so every link in every email would be relative "
                "to nothing.",
                hint="Set FRONTEND_URL to the site's public address, e.g. https://gabstep.com",
                id="accounts.E001",
            )
        )
    elif host in LOCAL_HOSTS:
        issues.append(
            Error(
                f"FRONTEND_URL is {url!r}, which only resolves on the machine that "
                "sent the mail. Every button in every email would be dead for the "
                "person who received it.",
                hint="Set FRONTEND_URL to the site's public address, e.g. https://gabstep.com",
                id="accounts.E002",
            )
        )
    elif host in DASHBOARD_HOSTS or host.endswith(".vercel.com"):
        issues.append(
            Warning(
                f"FRONTEND_URL is {url!r}, which is a hosting dashboard rather than "
                "the site. Every link in every email and the return address the "
                "payment provider sends people back to are both built from this, so "
                "all of them would land on a page the applicant cannot use.",
                hint=(
                    "Use the address a visitor types, e.g. "
                    "https://apply.gabstep.com"
                ),
                id="accounts.W004",
            )
        )
    elif urlparse(url).path.strip("/"):
        issues.append(
            Warning(
                f"FRONTEND_URL is {url!r}, which has a path on the end. This has to "
                "be the site's root, because the code appends its own paths to it: "
                f"a return address would come out as {url.rstrip('/')}/payment/...",
                hint="Drop everything after the hostname.",
                id="accounts.W005",
            )
        )
    elif urlparse(url).scheme != "https":
        issues.append(
            Warning(
                f"FRONTEND_URL is {url!r}. Emails carry sign-in links, so they should "
                "point at https.",
                id="accounts.W001",
            )
        )

    return issues


@register()
def check_email_is_configured(app_configs, **kwargs):
    """A live deployment that cannot send mail loses applicants silently.

    Sending happens on a background thread and a failure is logged rather than
    raised, which is right for a web request and wrong for a deployment: nobody
    finds out until someone asks why they never got their password.
    """
    issues = []
    if settings.DEBUG or "smtp" not in settings.EMAIL_BACKEND:
        return issues

    if not settings.EMAIL_HOST_PASSWORD:
        issues.append(
            Warning(
                "EMAIL_HOST_PASSWORD is not set, so no email can be sent: no welcome "
                "message, no status update, no letter notification.",
                hint="Set EMAIL_HOST_PASSWORD in the environment.",
                id="accounts.W003",
            )
        )
    return issues
