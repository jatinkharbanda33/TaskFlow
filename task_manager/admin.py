from django.contrib import admin
from .models import Task, AuditLog, Board


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "priority",
        "created_by",
        "assigned_to",
        "board",
        "due_date",
        "created_at",
        "is_overdue",
    )
    list_filter = ("status", "priority", "created_at", "board", "assigned_to")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at", "completed_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "description", "status", "priority")},
        ),
        ("Relationships", {"fields": ("board", "created_by", "assigned_to")}),
        ("Dates", {"fields": ("due_date", "completed_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action_type", "user", "description", "ip_address", "created_at")
    list_filter = ("action_type", "created_at")
    search_fields = ("description", "user__email")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
