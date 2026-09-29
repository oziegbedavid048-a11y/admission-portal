"""Email verification for accounts people create themselves.

An applicant or agent who signs up is sent a link, and cannot sign in until
they open it. Opening it confirms the address, signs them in, and sends the
welcome email that explains what they can do on the platform.

The link carries a signed token (django.core.signing) holding the account id
and the address it was sent to. It lasts VERIFY_EMAIL_MAX_AGE seconds (48 hours
by default), cannot be forged without SECRET_KEY, and stops matching if the
account's email address changes.

Accounts the desk creates (staff, sales managers) and students an agent files
are never asked to verify: `User.email_verified` defaults to True, and only the
two sign-up forms set it to False.
"""

from django.conf import settings
from django.core import signing

SALT = "gabstep.accounts.verify-email"


def max_age():
    return int(getattr(settings, "VERIFY_EMAIL_MAX_AGE", 48 * 3600))


def make_token(user):
    return signing.dumps({"u": user.pk, "e": user.email}, salt=SALT, compress=True)


def user_from_token(token):
    """The account a token was issued for, or None if it is invalid or expired."""
    from .models import User

    try:
        data = signing.loads(token or "", salt=SALT, max_age=max_age())
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None
    user = User.objects.filter(pk=data.get("u"), is_active=True).first()
    if user is None or (user.email or "").lower() != (data.get("e") or "").lower():
        return None
    return user


def send_verification(user):
    from .emails import _url, send_verification_email

    link = _url(f"/verify-email?token={make_token(user)}")
    return send_verification_email(user, link, max(1, max_age() // 3600))
