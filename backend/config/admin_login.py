"""The admin sign-in page, with a limit on wrong passwords.

The API's sign-in has rate limits and a per-account lockout, but /admin/login/
had nothing: anyone could guess the desk's passwords as fast as they liked. This
wraps the stock admin login and counts failed attempts in the cache:

* per address (the address the hosting edge saw, which the caller cannot
  spoof by sending headers; see config/throttles.py): 10 failures in 15 minutes;
* per account name: 20 failures in 15 minutes, so a guesser spreading across
  many addresses is stopped too, while one person mistyping is never near it.

A successful sign-in clears the counts for that address and account.
"""

import logging

from django.contrib import admin
from django.core.cache import cache
from django.http import HttpResponse

from config.throttles import edge_ip

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 15 * 60
MAX_PER_ADDRESS = 10
MAX_PER_ACCOUNT = 20


def _keys(request):
    address = edge_ip(request)
    account = (request.POST.get("username") or "").strip().lower()[:254]
    return f"admin-login:ip:{address}", f"admin-login:user:{account}" if account else None


def _blocked(ip_key, user_key):
    if (cache.get(ip_key) or 0) >= MAX_PER_ADDRESS:
        return True
    return bool(user_key) and (cache.get(user_key) or 0) >= MAX_PER_ACCOUNT


def _count(key):
    if not key:
        return
    if cache.add(key, 1, WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)


def _why_refused(request):
    """Why a sign-in was refused, for the host's log: no secret is written.

    The page itself says only "enter the correct email address and password",
    which cannot tell the desk whether the address, the password or the account
    is the problem. The typed address is logged only when it looks like one, so
    a password typed into the wrong box never reaches the log; the password is
    checked but never written.
    """
    from apps.accounts.models import User

    typed = (request.POST.get("username") or "").strip()
    if "@" not in typed or len(typed) > 120:
        return "the first box did not hold an email address"
    try:
        user = User.objects.get_by_natural_key(typed)
    except User.DoesNotExist:
        return f"no account has the address {typed.lower()}"
    if not user.check_password(request.POST.get("password") or ""):
        return f"the password does not match the account {user.email}"
    if not user.is_active:
        return f"the account {user.email} is switched off"
    if not user.is_staff:
        return f"the account {user.email} is not a staff account"
    return f"the account {user.email} was refused for another reason"


def limited_admin_login(request, extra_context=None):
    if request.method != "POST":
        return admin.site.login(request, extra_context=extra_context)

    ip_key, user_key = _keys(request)
    if _blocked(ip_key, user_key):
        return HttpResponse(
            "Too many sign-in attempts. Wait 15 minutes and try again.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )

    response = admin.site.login(request, extra_context=extra_context)
    if request.user.is_authenticated and request.user.is_staff:
        cache.delete(ip_key)
        if user_key:
            cache.delete(user_key)
    else:
        _count(ip_key)
        _count(user_key)
        logger.warning("Admin sign-in refused: %s.", _why_refused(request))
    return response
