"""Keeping test and mock-up accounts apart from real ones.

A user with ``is_test_account`` set is a test account, and so is everything that
hangs off it: an agent's profile, wallet, loans and withdrawals, and every
application it filed or owns, with the payments, documents and letters on them.

The admin never shows that data on a working screen. Each list that can hold it
uses ``RealDataOnlyAdmin``, which names the path from its rows to the users who
own them. The rows appear instead under the "Test accounts" section of the admin
(apps/testaccounts).

Only the lists are filtered. A record's own page, and the review, download and
confirm pages hanging off it, still open by id, so the links on the Test accounts
screens keep working. A list opened for one application or one agent
(``?application=`` or ``?agent=``) is a drill-down from a record staff already
picked, so it shows that record's rows too.
"""

from functools import reduce
from operator import or_

from django.db.models import Q

# Query-string keys that narrow a list to one record's rows.
DRILL_DOWN_PARAMS = ("application", "application_id", "agent")


def test_owner_q(*user_paths):
    """A Q matching rows owned by a test account.

    Each path leads from the row to a user, e.g. ``"application__applicant"``.
    An empty path means the row is the user.
    """
    return reduce(
        or_,
        (Q(**{f"{path}__is_test_account" if path else "is_test_account": True}) for path in user_paths),
    )


class RealDataOnlyAdmin:
    """Admin mixin: leave test-account rows off this list.

    Put it first in the bases, so every ``get_queryset`` further down the class
    passes through it. ``test_user_paths`` names the paths to the owning users.

    A Test accounts screen built on a working screen sets ``test_data_only``,
    which turns the filter round: only test-account rows, on every page.
    """

    test_user_paths = ()
    test_data_only = False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not self.test_user_paths:
            return queryset
        if self.test_data_only:
            return queryset.filter(test_owner_q(*self.test_user_paths))
        if self._hides_test_data(request):
            queryset = queryset.exclude(test_owner_q(*self.test_user_paths))
        return queryset

    def _hides_test_data(self, request):
        match = getattr(request, "resolver_match", None)
        url_name = getattr(match, "url_name", "") or ""
        # Lists and the pickers that search them. A record's own page is
        # reached by id from a screen that already chose it.
        if not (url_name.endswith("_changelist") or url_name == "autocomplete"):
            return False
        return not any(request.GET.get(key) for key in DRILL_DOWN_PARAMS)


def without_test_addresses(addresses):
    """The addresses that do not belong to a test account."""
    from apps.accounts.models import User

    addresses = [address for address in addresses if address]
    if not addresses:
        return []
    lowered = {address.strip().lower() for address in addresses}
    test = set(
        User.objects.filter(email__in=lowered, is_test_account=True).values_list("email", flat=True)
    )
    return [address for address in addresses if address.strip().lower() not in test]
