"""The admin's Test accounts section.

Test and mock-up accounts (``User.is_test_account``) are kept off every working
admin screen so they never mix with real applicants and agents. These proxies
give them a section of their own. They add no tables: each is a filtered view of
an existing model. See apps/accounts/testdata.py.
"""

from apps.accounts.models import User
from apps.applications.models import Application
from apps.partners.models import AgentProfile


class TestAgent(AgentProfile):
    """A partner agent account used for testing."""

    class Meta:
        proxy = True
        app_label = "testaccounts"
        verbose_name = "test agent"
        verbose_name_plural = "test agents"


class TestApplication(Application):
    """An application owned by, or filed by, a test account."""

    class Meta:
        proxy = True
        app_label = "testaccounts"
        verbose_name = "test application"
        verbose_name_plural = "test applications"


class TestUser(User):
    """Every account marked as a test account."""

    class Meta:
        proxy = True
        app_label = "testaccounts"
        verbose_name = "test user"
        verbose_name_plural = "test users"
