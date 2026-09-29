from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SupportReply, SupportTicket, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "full_name", "role", "email_verified", "is_active", "date_joined")
    list_filter = ("role", "email_verified", "is_active", "is_staff")
    actions = ("action_mark_email_verified", "action_resend_verification")
    search_fields = ("email", "full_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "country", "avatar", "role", "email_verified")}),
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

    @admin.action(description="Mark email as verified")
    def action_mark_email_verified(self, request, queryset):
        count = queryset.filter(email_verified=False).update(email_verified=True)
        self.message_user(request, f"{count} account(s) marked verified.", messages.SUCCESS)

    @admin.action(description="Resend verification email")
    def action_resend_verification(self, request, queryset):
        from .verification import send_verification

        pending = list(queryset.filter(email_verified=False, is_active=True))
        for user in pending:
            send_verification(user)
        skipped = queryset.count() - len(pending)
        self.message_user(request, f"Verification email sent to {len(pending)} account(s).", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"{skipped} skipped: already verified or inactive.", messages.INFO)


class SupportTicketForm(forms.ModelForm):
    reply = forms.CharField(
        label="Reply",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "style": "width: 100%;"}),
        help_text=(
            "Write your answer and press Save. It is emailed to the sender and "
            "shown under their message on their Support page."
        ),
    )
    resolve_after_reply = forms.BooleanField(
        label="Mark resolved after sending", required=False, initial=True
    )

    class Meta:
        model = SupportTicket
        fields = ("status",)


class SupportReplyInline(admin.TabularInline):
    """What the desk has already answered. Read-only: a sent email cannot be unsent."""

    model = SupportReply
    extra = 0
    can_delete = False
    fields = ("created_at", "author", "body", "emailed")
    readonly_fields = fields
    max_num = 0


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Messages sent from the Support page in any portal.

    Each one is emailed to the support inbox as it arrives. Answer it here: type
    in Reply and save, and the answer is emailed to the sender and appears under
    their message on their Support page.
    """

    form = SupportTicketForm
    inlines = (SupportReplyInline,)

    list_display = ("reference", "subject", "sender", "topic", "status", "emailed", "created_at")
    list_filter = ("status", "topic", "emailed", "created_at")
    search_fields = ("reference", "subject", "message", "user__email", "user__full_name")
    date_hierarchy = "created_at"
    readonly_fields = (
        "reference", "user", "topic", "subject", "message", "attachment_link",
        "emailed", "created_at", "resolved_at",
    )
    fieldsets = (
        (None, {"fields": (("reference", "status"), ("user", "topic"), "subject", "message", "attachment_link")}),
        ("Reply", {"fields": ("reply", "resolve_after_reply")}),
        ("Delivery", {"fields": (("emailed", "created_at", "resolved_at"),)}),
    )
    list_display = ("reference", "subject", "sender", "topic", "status", "reply_count", "emailed", "created_at")
    actions = ("action_mark_resolved", "action_reopen", "action_email_inbox_again")

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

    @admin.display(description="Replies")
    def reply_count(self, obj):
        return obj.replies.count()

    def save_model(self, request, obj, form, change):
        from .emails import send_support_reply_email

        body = (form.cleaned_data.get("reply") or "").strip()
        if body and form.cleaned_data.get("resolve_after_reply"):
            obj.status = SupportTicket.Status.RESOLVED
        if obj.status == SupportTicket.Status.RESOLVED and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        elif obj.status == SupportTicket.Status.OPEN:
            obj.resolved_at = None
        super().save_model(request, obj, form, change)

        if body:
            reply = SupportReply.objects.create(ticket=obj, author=request.user, body=body)
            reply.emailed = send_support_reply_email(reply)
            reply.save(update_fields=["emailed"])
            if reply.emailed:
                self.message_user(request, f"Reply emailed to {obj.user.email}.", messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    "The reply is saved and shows on their Support page, but the email "
                    "could not be sent. Run `manage.py mail_check` on the server to see why.",
                    messages.WARNING,
                )

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


    @admin.action(description="Email to the support inbox again")
    def action_email_inbox_again(self, request, queryset):
        """For messages whose first email failed, once mail is working."""
        from .emails import send_support_ticket_email

        sent = 0
        for ticket in queryset.filter(emailed=False):
            if send_support_ticket_email(ticket):
                ticket.emailed = True
                ticket.save(update_fields=["emailed"])
                sent += 1
        failed = queryset.filter(emailed=False).count()
        if sent:
            self.message_user(request, f"{sent} message(s) emailed to the support inbox.", messages.SUCCESS)
        if failed:
            self.message_user(
                request,
                f"{failed} could not be sent. Run `manage.py mail_check` on the server to see why.",
                messages.ERROR,
            )
