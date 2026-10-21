"""One shape for every API error.

DRF answers its own errors (validation, permission, not found, rate limit) as
JSON with a `detail`. Anything else, a bug or a database hiccup, escaped to
Django and came back as the HTML "Server Error (500)" page, which the portal
cannot read and has to guess about. This catches those too: the full error goes
to the log, the caller gets a plain sentence and a code, and nothing about the
server's internals.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler, set_rollback

logger = logging.getLogger("gabstep.api")

SERVER_ERROR = "Something went wrong on our side. Please try again in a moment."


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, DjangoValidationError):
        # A model's own rule refusing a value is the caller's mistake, not ours.
        set_rollback()
        return Response(
            {"detail": " ".join(exc.messages), "code": "invalid"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    request = context.get("request")
    logger.exception(
        "Unhandled error on %s %s",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        exc_info=exc,
    )
    # Whatever the view wrote before failing is undone, as it would have been
    # had the error reached Django.
    set_rollback()
    return Response(
        {"detail": SERVER_ERROR, "code": "server_error"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
