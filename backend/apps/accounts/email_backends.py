"""Sending mail over HTTPS instead of SMTP.

Render does not allow outbound SMTP on its cheaper instances. The symptom is a
connection that never opens:

    Email failed: 'Your Gabstep account' to [...]: timed out

Nothing in the application can fix that, because the block is below it. But mail
providers all offer an HTTPS API, and HTTPS is ordinary web traffic that no host
blocks, so the way out is to stop using SMTP.

This is a Django email backend that posts to a provider's API. It speaks Resend
and Brevo, which both accept a single JSON request and need only an API key.
Pick one with EMAIL_PROVIDER and give it a key; everything that sends mail
carries on calling `django.core.mail` and does not know the difference.

Keeping it a backend rather than a special case inside the senders matters: the
welcome email, the status updates, the payout notices and the admin's own error
mail all go the same way, and switching provider is one setting.
"""

import json
import logging
from urllib import error, request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

TIMEOUT = 20

ENDPOINTS = {
    "resend": "https://api.resend.com/emails",
    "brevo": "https://api.brevo.com/v3/smtp/email",
}


def _split_address(address):
    """"Name <a@b.c>" into ("Name", "a@b.c"). Either part may be missing."""
    address = (address or "").strip()
    if address.endswith(">") and "<" in address:
        name, _, rest = address.rpartition("<")
        return name.strip().strip('"'), rest[:-1].strip()
    return "", address


class HttpEmailBackend(BaseEmailBackend):
    """Post each message to the provider's API.

    `send_messages` returns the number that were accepted, which is what Django
    promises and what the credentials email relies on: it only records itself as
    sent when the count comes back positive.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.provider = (getattr(settings, "EMAIL_PROVIDER", "") or "resend").lower()
        self.api_key = getattr(settings, "EMAIL_PROVIDER_API_KEY", "") or ""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            logger.error(
                "EMAIL_PROVIDER_API_KEY is not set, so no mail can be sent over HTTPS."
            )
            if not self.fail_silently:
                raise ValueError("EMAIL_PROVIDER_API_KEY is not set.")
            return 0

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    # ── One message ──────────────────────────────────────────────────

    def _send(self, message):
        recipients = list(message.to or [])
        if not recipients:
            return False

        html = ""
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                html = content
                break

        try:
            url, payload, headers = self._request_for(message, recipients, html)
        except ValueError as exc:
            logger.error("Cannot send mail: %s", exc)
            if not self.fail_silently:
                raise
            return False

        req = request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=TIMEOUT) as response:
                logger.info(
                    "Email sent over HTTPS via %s: %r to %s (HTTP %s)",
                    self.provider, message.subject, recipients, response.status,
                )
                return True
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode(errors="replace")[:300]
            except Exception:
                pass
            # The provider's own message says what is wrong far better than a
            # generic failure: an unverified sending domain is the usual one.
            logger.error(
                "%s refused %r to %s: HTTP %s %s",
                self.provider, message.subject, recipients, exc.code, body,
            )
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            logger.error(
                "Could not reach %s to send %r to %s: %s",
                self.provider, message.subject, recipients, exc,
            )

        if not self.fail_silently:
            raise RuntimeError(f"{self.provider} did not accept the message.")
        return False

    def _request_for(self, message, recipients, html):
        sender = message.from_email or settings.DEFAULT_FROM_EMAIL
        name, address = _split_address(sender)

        if self.provider == "resend":
            payload = {
                "from": sender,
                "to": recipients,
                "subject": message.subject,
                "text": message.body,
            }
            if html:
                payload["html"] = html
            if message.cc:
                payload["cc"] = list(message.cc)
            if message.reply_to:
                payload["reply_to"] = list(message.reply_to)
            return (
                ENDPOINTS["resend"],
                payload,
                {"Authorization": f"Bearer {self.api_key}"},
            )

        if self.provider == "brevo":
            payload = {
                "sender": {"email": address, **({"name": name} if name else {})},
                "to": [{"email": to} for to in recipients],
                "subject": message.subject,
                "textContent": message.body,
            }
            if html:
                payload["htmlContent"] = html
            if message.cc:
                payload["cc"] = [{"email": cc} for cc in message.cc]
            return ENDPOINTS["brevo"], payload, {"api-key": self.api_key}

        raise ValueError(
            f"EMAIL_PROVIDER is {self.provider!r}; expected 'resend' or 'brevo'."
        )
