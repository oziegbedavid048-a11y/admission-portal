"""What an error report is allowed to show.

Django masks settings whose name matches API, TOKEN, KEY, SECRET, PASS or
SIGNATURE. `DATABASE_URL` matches none of those, and it carries the database
password in the middle of it, so a traceback or a `django.request` log with the
settings attached would print the credentials to the whole database.

DEBUG is off in production, so a traceback is not served to a visitor. This is for
everything else that reads the settings: an error-tracking integration, the
`manage.py diffsettings` output, a support dump someone pastes into an issue.
"""

import re

from django.views.debug import SafeExceptionReporterFilter


class GabstepReporterFilter(SafeExceptionReporterFilter):
    """Django's filter, plus the names that carry a credential without saying so."""

    hidden_settings = re.compile(
        # Django's own list.
        r"API|TOKEN|KEY|SECRET|PASS|SIGNATURE"
        # A connection string with the password inside it.
        r"|DATABASE_URL|DSN"
        # Anything naming an account money is sent to or taken from.
        r"|ACCOUNT|BENEFICIARY"
        # The SMTP mailbox.
        r"|EMAIL_HOST_USER",
        flags=re.IGNORECASE,
    )
