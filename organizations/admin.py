from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from .models import Organization, Domain, SubscriptionPlan, Subscription


@admin.register(Organization)
class OrganizationAdmin(TenantAdminMixin, admin.ModelAdmin):
    """Admin interface for Organization model."""

    list_display = (
        "business_name",
        "owner_email",
        "billing_email",
        "email_domain",
        "subscription",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "created_at", "subscription")
    search_fields = ("business_name", "owner_email", "billing_email", "email_domain")
    readonly_fields = ("organization_id", "created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "organization_id",
                    "business_name",
                    "owner_email",
                    "is_active",
                )
            },
        ),
        (
            "Billing Information",
            {"fields": ("billing_email", "billing_address", "contact_number")},
        ),
        (
            "Signup Settings",
            {"fields": ("email_domain",)},
        ),
        ("Subscription", {"fields": ("subscription",)}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for Subscription model."""

    list_display = (
        "subscription_id",
        "subscription_plan",
        "billing_cycle",
        "is_active",
        "end_date",
        "next_payment_date",
        "started_at",
    )
    list_filter = ("is_active", "billing_cycle", "started_at", "end_date")
    search_fields = ("subscription_id", "stripe_id", "subscription_plan__display_name")
    readonly_fields = (
        "subscription_id",
        "started_at",
        "expired_at",
        "last_payment_date",
    )

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("subscription_id", "subscription_plan", "is_active")},
        ),
        (
            "Billing Details",
            {
                "fields": (
                    "billing_cycle",
                    "stripe_id",
                    "end_date",
                    "next_payment_date",
                    "last_payment_date",
                )
            },
        ),
        ("Dates", {"fields": ("started_at", "expired_at"), "classes": ("collapse",)}),
    )


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin interface for SubscriptionPlan model."""

    list_display = (
        "display_name",
        "price",
        "currency",
        "max_users",
        "max_tasks",
        "created_at",
    )
    list_filter = ("currency", "created_at")
    search_fields = ("display_name", "description")
    readonly_fields = ("subscription_plan_id", "created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("subscription_plan_id", "display_name", "description")},
        ),
        ("Pricing", {"fields": ("price", "currency")}),
        ("Limits", {"fields": ("max_users", "max_tasks")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    """Admin interface for Domain model."""

    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain", "tenant__business_name")
    readonly_fields = ("id",) if hasattr(Domain, "id") else ()
