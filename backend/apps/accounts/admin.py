from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SupportTicket, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "full_name", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "country", "avatar", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Messages sent from the Support page in any portal.

    Each one was also emailed to the support inbox, with the sender as reply-to,
    so the conversation itself happens by email. This is the list of what came
    in and whether it has been dealt with.
    """

    list_display = ("reference", "subject", "sender", "topic", "status", "emailed", "created_at")
    list_filter = ("status", "topic", "emailed", "created_at")
    search_fields = ("reference", "subject", "message", "user__email", "user__full_name")
    date_hierarchy = "created_at"
    readonly_fields = (
        "reference", "user", "topic", "subject", "message", "attachment_link",
        "emailed", "created_at", "resolved_at",
    )
    fields = (
        ("reference", "status"),
        ("user", "topic"),
        "subject",
        "message",
        "attachment_link",
        ("emailed", "created_at", "resolved_at"),
    )
    actions = ("action_mark_resolved", "action_reopen")

    def has_add_permission(self, request):
        return False

    @admin.display(description="From", ordering="user__email")
    def sender(self, obj):
        return f"{obj.user.full_name or obj.user.email} ({obj.user.get_role_display()})"

    @admin.display(description="Attachment")
    def attachment_link(self, obj):
        if not obj.attachment:
            return "None"
        return format_html('<a href="{}" target="_blank" rel="noopener">Open</a>', obj.attachment.url)

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.resolved_at = timezone.now() if obj.status == SupportTicket.Status.RESOLVED else None
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark resolved")
    def action_mark_resolved(self, request, queryset):
        count = queryset.exclude(status=SupportTicket.Status.RESOLVED).update(
            status=SupportTicket.Status.RESOLVED, resolved_at=timezone.now()
        )
        self.message_user(request, f"{count} message(s) marked resolved.", messages.SUCCESS)

    @admin.action(description="Reopen")
    def action_reopen(self, request, queryset):
        count = queryset.exclude(status=SupportTicket.Status.OPEN).update(
            status=SupportTicket.Status.OPEN, resolved_at=None
        )
        self.message_user(request, f"{count} message(s) reopened.", messages.INFO)
