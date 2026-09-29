from django.contrib import admin

from .models import StoredFile


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    """Read-only view of what the uploads take up. Files are managed from the
    record they belong to (a document, a letter), never from here."""

    list_display = ("name", "content_type", "size_kb", "created_at")
    search_fields = ("name",)
    date_hierarchy = "created_at"
    fields = ("name", "content_type", "size", "created_at")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("content")

    @admin.display(description="Size", ordering="size")
    def size_kb(self, obj):
        return f"{obj.size / 1024:,.0f} KB"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
