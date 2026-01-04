from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserAccount


@admin.register(UserAccount)
class UserAccountAdmin(UserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_restricted",
        "organization",
    )
    list_filter = (
        "is_staff",
        "is_active",
        "is_restricted",
        "organization",
        "is_org_owner",
        "is_admin",
    )
    search_fields = ("email", "first_name", "last_name", "organization__business_name")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name")}),
        ("Organization", {"fields": ("organization",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_restricted",
                    "is_staff",
                    "is_admin",
                    "is_org_owner",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "organization",
                ),
            },
        ),
    )

    readonly_fields = ("date_joined", "last_login")
