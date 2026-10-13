"""Test accounts: the admin screens for test and mock-up data.

Each screen is the working screen it is named after, turned round to show only
test-account rows (``test_data_only``). Opening a test agent lists the students
they registered; opening a student uses the same review pages as a real file.
"""

from django.contrib import admin
from django.urls import reverse

from apps.accounts.admin import UserAdmin
from apps.applications.admin import AgentApplicationAdmin, AgentApplicationsAdmin
from config.admin_ui import button_link

from .models import TestAgent, TestApplication, TestUser


@admin.register(TestAgent)
class TestAgentAdmin(AgentApplicationsAdmin):
    """Test agents. Click one to see the students it registered."""

    test_data_only = True

    def get_model_perms(self, request):
        return admin.ModelAdmin.get_model_perms(self, request)


@admin.register(TestApplication)
class TestApplicationAdmin(AgentApplicationAdmin):
    """Every application owned or filed by a test account."""

    test_data_only = True
    filed_by_agent = None

    def get_urls(self):
        # The download page is AgentApplicationAdmin's, reached by its own name.
        # Registering it again here would give two pages the same URL name.
        return super(AgentApplicationAdmin, self).get_urls()

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), "title": "Test applications"})

    @admin.display(description="")
    def download(self, obj):
        if not obj.submitted_by_agent_id:
            return ""
        return super().download(obj)


@admin.register(TestUser)
class TestUserAdmin(UserAdmin):
    """Every account marked as a test account.

    Untick "Is test account" on a user to move it, and everything it owns, back
    to the working screens.
    """

    test_data_only = True
    actions = ()
    list_display = ("email", "full_name", "role", "is_active", "date_joined", "open_agent")

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        # Skip UserAdmin's send-message page: it is registered under its own name.
        return super(UserAdmin, self).get_urls()

    @admin.display(description="")
    def open_agent(self, obj):
        profile = getattr(obj, "agent_profile", None)
        if not profile:
            return ""
        return button_link(
            reverse("admin:applications_agentapplication_changelist") + f"?agent={profile.pk}",
            "View students",
        )
