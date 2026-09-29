"""Sessions end when the password changes.

A sign-in token carries a short fingerprint of the account's password hash.
Changing or resetting the password changes the hash, so every token issued
before that stops working: the access token on its next request, the refresh
cookie on its next refresh. That is what makes "reset my password" actually lock
out whoever had the old one.

The fingerprint is an HMAC of the stored hash under SECRET_KEY, cut short. It
reveals nothing about the password, and it cannot be forged without the key.
Tokens issued before this existed carry no fingerprint and are accepted until
they expire on their own.
"""

import hashlib
import hmac

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

CLAIM = "pwd"


def password_fingerprint(user):
    digest = hmac.new(
        settings.SECRET_KEY.encode(), (user.password or "").encode(), hashlib.sha256
    ).hexdigest()
    return digest[:16]


def stamp(token, user):
    """Add the fingerprint (and the display claims) to a refresh token."""
    token["role"] = user.role
    token["full_name"] = user.full_name
    token[CLAIM] = password_fingerprint(user)
    return token


def token_matches(token, user):
    claimed = token.get(CLAIM) if hasattr(token, "get") else None
    return claimed is None or hmac.compare_digest(str(claimed), password_fingerprint(user))


class GabstepJWTAuthentication(JWTAuthentication):
    """The standard JWT check, plus: the password has not changed since."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not token_matches(validated_token, user):
            raise InvalidToken("Your password was changed. Sign in again.")
        return user
