from django.contrib import admin
from .models import Task, ScheduledTask, AuditLog, Board


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "priority",
        "created_by",
        "board",
        "due_date",
        "created_at",
        "is_overdue",
    )
    list_filter = ("status", "priority", "created_at", "board")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at", "completed_at")
    filter_horizontal = ("assigned_to",)
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


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "priority",
        "scheduled_time",
        "processing_status",
        "due_date",
        "created_at",
        "board",
    )
    list_filter = ("status", "processing_status", "created_at")
    search_fields = ("title", "description")
    readonly_fields = ("created_at",)
    date_hierarchy = "scheduled_time"


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
