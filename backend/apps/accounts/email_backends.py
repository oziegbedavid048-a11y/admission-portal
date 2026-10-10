"""Sending mail over HTTPS instead of SMTP.

Render does not allow outbound SMTP on its cheaper instances. The symptom is a
connection that never opens:

    Email failed: 'Your Gabstep account' to [...]: timed out

Nothing in the application can fix that, because the block is below it. But mail
providers all offer an HTTPS API, and HTTPS is ordinary web traffic that no host
blocks, so the way out is to stop using SMTP.

This is a Django email backend that posts to a provider's API. It speaks Zoho
ZeptoMail, Resend and Brevo, which all accept a single JSON request and need only
an API key. Pick one with EMAIL_PROVIDER and give it a key; everything that sends
mail carries on calling `django.core.mail` and does not know the difference.

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
    # Zoho ZeptoMail. The host differs by the region the account was created in,
    # so it is a setting rather than a constant: cpaas.zoho.com for zoho.com,
    # and there are .eu and .in equivalents.
    "zeptomail": "https://{host}/v1.1/email",
}

ZEPTOMAIL_DEFAULT_HOST = "cpaas.zoho.com"
ZEPTOMAIL_SCHEME = "Zoho-enczapikey"


def _clean_host(value, fallback):
    """A bare hostname, whatever shape it arrived in.

    The provider's console shows a host, and a host is what this needs, but it is
    natural to paste the whole URL. Left alone, "https://cpaas.zoho.com" builds
    "https://https://cpaas.zoho.com/v1.1/email", and the failure is a DNS error
    that says nothing about a stray scheme:

        <urlopen error [Errno -2] Name or service not known>

    So the scheme, any path, and any stray whitespace come off.
    """
    host = (value or "").strip()
    if not host:
        return fallback
    if "//" in host:
        host = host.split("//", 1)[1]
    host = host.split("/", 1)[0].strip().strip(".")
    if "cpass.zoho" in host.lower():
        host = host.lower().replace("cpass.zoho", "cpaas.zoho")
    return host or fallback


def _provider_detail(body):
    """The human-readable part of a provider's error response.

    Every one of them answers with JSON, and every one nests the useful sentence
    somewhere different. Whatever is found is better than a generic message,
    because the three common failures -- key rejected, sending domain not
    verified, account out of credit -- are indistinguishable without it.
    """
    if not body:
        return ""
    try:
        data = json.loads(body)
    except ValueError:
        return body.strip()[:200]

    error_block = data.get("error") if isinstance(data, dict) else None
    if isinstance(error_block, dict):
        parts = []
        for item in error_block.get("details") or []:
            if isinstance(item, dict) and item.get("message"):
                parts.append(item["message"])
        headline = error_block.get("message") or ""
        if parts:
            return f"{headline} ({'; '.join(parts)})".strip()
        if headline:
            return headline
    for key in ("message", "detail", "error_description"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, str) and value:
            return value
    return body.strip()[:200]


def _zeptomail_authorization(api_key):
    """The Authorization header ZeptoMail wants.

    Its console presents the key already prefixed with the scheme, and the prefix
    is easy to end up with twice: once from the console and once from whoever
    added it. Either form is accepted here, and exactly one prefix is sent.
    """
    # A copy from the console can also carry the header name and its colon,
    # "Zoho-enczapikey: Zoho-enczapikey <key>", so a colon after the prefix goes too.
    key = (api_key or "").strip()
    while key.lower().startswith(ZEPTOMAIL_SCHEME.lower()):
        key = key[len(ZEPTOMAIL_SCHEME):].strip().lstrip(":").strip()
    return f"{ZEPTOMAIL_SCHEME} {key}"


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
        # The provider's own words about the last failure, for a caller to show.
        self.last_error = None

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
                body = exc.read().decode(errors="replace")[:400]
            except Exception:
                pass
            # The provider's own message says what is wrong far better than any
            # generic failure could: an unverified sending domain, a rejected key,
            # or an account out of credit all look identical otherwise. It is kept
            # on the exception so a caller can show it rather than guess.
            detail = _provider_detail(body) or f"HTTP {exc.code}"
            logger.error(
                "%s refused %r to %s: HTTP %s %s",
                self.provider, message.subject, recipients, exc.code, body,
            )
            self.last_error = detail
        except (error.URLError, TimeoutError, OSError, ValueError) as exc:
            logger.error(
                "Could not reach %s at %s to send %r to %s: %s",
                self.provider, url, message.subject, recipients, exc,
            )
            self.last_error = f"could not reach {url}: {exc}"

        if not self.fail_silently:
            raise RuntimeError(
                f"{self.provider} did not accept the message: "
                f"{getattr(self, 'last_error', None) or 'no detail given'}"
            )
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

        if self.provider == "zeptomail":
            payload = {
                "from": {"address": address, **({"name": name} if name else {})},
                "to": [
                    {"email_address": {"address": to}} for to in recipients
                ],
                "subject": message.subject,
                "textbody": message.body,
            }
            if html:
                payload["htmlbody"] = html
            if message.cc:
                payload["cc"] = [{"email_address": {"address": cc}} for cc in message.cc]
            if message.reply_to:
                reply = _split_address(message.reply_to[0])[1]
                payload["reply_to"] = [{"address": reply}]
            # Attachments (e.g. PDF certificates) - ZeptoMail accepts base64
            raw_attachments = getattr(message, "attachments", None)
            if raw_attachments:
                import base64
                encoded = []
                for att in raw_attachments:
                    if isinstance(att, tuple):
                        att_name, att_content, att_mime = att
                    else:
                        att_name = att.get_filename() or "attachment"
                        att_content = att.get_payload(decode=True)
                        att_mime = att.get_content_type()
                    if isinstance(att_content, str):
                        att_content = att_content.encode()
                    encoded.append({
                        "name": att_name,
                        "content": base64.b64encode(att_content).decode(),
                        "mime_type": att_mime,
                    })
                if encoded:
                    payload["attachments"] = encoded
            host = _clean_host(
                getattr(settings, "ZEPTOMAIL_HOST", ""), ZEPTOMAIL_DEFAULT_HOST
            )
            return (
                ENDPOINTS["zeptomail"].format(host=host),
                payload,
                {"Authorization": _zeptomail_authorization(self.api_key)},
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
            f"EMAIL_PROVIDER is {self.provider!r}; expected 'zeptomail', 'resend' "
            "or 'brevo'."
        )
