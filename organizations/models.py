from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
import uuid  # Requires: pip install uuid6


class SubscriptionPlan(models.Model):
    """
    Defines available billing tiers.
    Living in public schema, shared reference for all tenants.
    """

    PLAN_TIERS = (
        ("FREE", "Free"),
        ("STARTER", "Starter"),
        ("PRO", "Pro"),
        ("ENTERPRISE", "Enterprise"),
    )
    CURRENCY_CHOICES = (("USD", "US Dollar"), ("IND", "Indian Rupee"))

    subscription_plan_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    display_name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default="USD", db_index=True
    )

    # Limits
    max_users = models.IntegerField(default=5)
    max_tasks = models.IntegerField(default=100)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["currency", "price"]),
        ]

    def __str__(self):
        return f"{self.display_name} {self.currency} (${self.price})"


class Subscription(models.Model):
    BILLING_OPTIONS = (("MONTHLY", "Monthly"), ("YEARLY", "Yearly"))
    subscription_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    subscription_plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, db_index=True
    )
    is_active = models.BooleanField(
        default=True, help_text="Kill-switch for the tenant", db_index=True
    )

    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    end_date = models.DateField(db_index=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    billing_cycle = models.CharField(
        max_length=10, choices=BILLING_OPTIONS, db_index=True
    )
    stripe_id = models.CharField(max_length=255, unique=True, db_index=True)
    next_payment_date = models.DateField(db_index=True)
    last_payment_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["is_active", "end_date"]),
            models.Index(fields=["billing_cycle", "is_active"]),
        ]

    def __str__(self):
        return f"Subscription {self.subscription_id} - {self.subscription_plan}"


class Organization(TenantMixin):
    """
    The Tenant Model.
    Represents a customer account/company.
    """

    organization_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    business_name = models.CharField(max_length=100, db_index=True)
    owner_email = models.EmailField(
        help_text="Email of the organization owner", db_index=True
    )

    # SUBSCRIPTION:
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, db_index=True
    )
    is_active = models.BooleanField(
        default=True, help_text="Kill-switch for the tenant", db_index=True
    )

    # METADATA
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Billing Info
    billing_email = models.EmailField(help_text="Email for billing", db_index=True)
    billing_address = models.TextField(help_text="Address for billing")
    contact_number = models.CharField(max_length=20, blank=True)

    # Email Domain for Signup
    email_domain = models.CharField(
        max_length=255,
        help_text="Email domain allowed for sisgnup (e.g., 'company.com')",
        db_index=True,
    )

    # Default true for django-tenants to handle schema creation automatically
    auto_create_schema = True

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "business_name"]),
            models.Index(fields=["owner_email", "is_active"]),
        ]

    def __str__(self):
        return self.business_name


class Domain(DomainMixin):
    """
    The Domain Model.
    Routes requests (e.g., tenant.app.com) to the correct Schema.
    """

    pass
