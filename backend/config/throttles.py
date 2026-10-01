"""Rate limits, and how a caller's address is worked out for them.

Requests reach Django along two paths:

* through the site on Vercel, which rewrites /api/ to Render. Vercel overwrites
  X-Forwarded-For with the real client address, so its first entry can be
  trusted on this path;
* straight to the onrender.com host. Render's proxy appends to whatever
  X-Forwarded-For the caller sent and strips nothing, so here the first entry
  is whatever the caller typed.

DRF's default identity was the whole X-Forwarded-For string, so a caller who
sent a new random value with every request got a fresh allowance every time
and no anonymous limit held. Two layers replace it:

1. Every per-endpoint limit (sign-in, sign-up, password reset...) counts per
   *client*: the first forwarded address. That is exact for everyone using the
   site through Vercel.
2. A looser limit counts per *connection*: the address the hosting edge itself
   saw (Cloudflare's CF-Connecting-IP / True-Client-IP in front of Render,
   else the socket address). Spoofing X-Forwarded-For does not change it, so
   someone going straight to Render is held to this however they vary the
   header. Requests that come through Vercel share Vercel's addresses here,
   which is why this limit sits far above anything one person does.

The "money" limit also never applied: the throttles that used it subclassed
ScopedRateThrottle, which takes its scope from the view's `throttle_scope` and
lets everything through when a view has none. They now carry their own scope.
"""

import ipaddress

from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    SimpleRateThrottle,
    UserRateThrottle,
)

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def _valid_ip(value):
    value = (value or "").strip()
    if not value or len(value) > 45:
        return ""
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def forwarded_client_ip(request):
    """The client as the first proxy saw it, or the socket address."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    first = _valid_ip(forwarded.split(",")[0]) if forwarded else ""
    return first or request.META.get("REMOTE_ADDR", "") or "unknown"


def edge_ip(request):
    """The address that connected to the hosting edge. Not caller-controlled
    on Render, where Cloudflare sets these headers on every request."""
    for header in ("HTTP_CF_CONNECTING_IP", "HTTP_TRUE_CLIENT_IP"):
        found = _valid_ip(request.META.get(header))
        if found:
            return found
    return request.META.get("REMOTE_ADDR", "") or "unknown"


class ClientIdentMixin:
    def get_ident(self, request):
        return forwarded_client_ip(request)


class AnonThrottle(ClientIdentMixin, AnonRateThrottle):
    """The floor for anonymous requests, per client."""


class UserThrottle(ClientIdentMixin, UserRateThrottle):
    """The floor for signed-in requests, per account (per client when anonymous)."""


class ScopedThrottle(ClientIdentMixin, ScopedRateThrottle):
    """A view's `throttle_scope`, per account or per client."""


class EdgeThrottle(SimpleRateThrottle):
    """Anonymous requests per connecting address, whatever headers they carry."""

    scope = "edge"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": edge_ip(request)}


class MoneyThrottle(UserThrottle):
    """Anything that moves money, held well below what a person would ever do.

    Reading a wallet or a list of withdrawals is not limited by this; only the
    requests that create or change something are.
    """

    scope = "money"

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class UploadThrottle(UserThrottle):
    """Files sent to be stored. Every one lands in the database, so a script
    sending thousands could fill it. Set well above an agent uploading the
    documents for a class of students in an hour."""

    scope = "upload"

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class CheckoutThrottle(UserThrottle):
    """Starting a payment or sending a transfer receipt. Looser than "money":
    an agent paying for a class of students does this many times in an hour."""

    scope = "checkout"


class PaymentStatusThrottle(UserThrottle):
    """The payment return page polls a few times; a script asking thousands of
    times (each one a call to Paystack) is stopped."""

    scope = "payment_status"
