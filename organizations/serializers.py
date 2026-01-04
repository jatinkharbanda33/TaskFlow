from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Organization, Domain


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for SubscriptionPlan model.
    Used for displaying available plans to users.
    """

    subscription_plan_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            "subscription_plan_id",
            "display_name",
            "description",
            "price",
            "currency",
            "max_users",
            "max_tasks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["subscription_plan_id", "created_at", "updated_at"]

    def validate_price(self, value):
        """Ensure price is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_max_users(self, value):
        """Ensure max_users is positive"""
        if value <= 0:
            raise serializers.ValidationError("Max users must be greater than 0.")
        return value

    def validate_max_tasks(self, value):
        """Ensure max_tasks is positive"""
        if value <= 0:
            raise serializers.ValidationError("Max tasks must be greater than 0.")
        return value


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing subscription plans.
    Excludes internal fields.
    """

    subscription_plan_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            "subscription_plan_id",
            "display_name",
            "description",
            "price",
            "currency",
            "max_users",
            "max_tasks",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Subscription model.
    Handles subscription details with proper field visibility.
    """

    subscription_id = serializers.UUIDField(read_only=True)
    subscription_plan = SubscriptionPlanSerializer(read_only=True)
    subscription_plan_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    started_at = serializers.DateTimeField(read_only=True)
    expired_at = serializers.DateTimeField(read_only=True)
    last_payment_date = serializers.DateField(read_only=True)
    stripe_id = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=255
    )

    class Meta:
        model = Subscription
        fields = [
            "subscription_id",
            "subscription_plan",
            "subscription_plan_id",
            "is_active",
            "started_at",
            "end_date",
            "expired_at",
            "billing_cycle",
            "stripe_id",
            "next_payment_date",
            "last_payment_date",
        ]
        read_only_fields = [
            "subscription_id",
            "started_at",
            "expired_at",
            "last_payment_date",
            "is_active",
        ]

    def validate_billing_cycle(self, value):
        """Validate billing cycle choice"""
        valid_choices = [choice[0] for choice in Subscription.BILLING_OPTIONS]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Billing cycle must be one of: {', '.join(valid_choices)}"
            )
        return value

    def validate_end_date(self, value):
        """Ensure end_date is in the future"""
        from django.utils import timezone

        if value <= timezone.now().date():
            raise serializers.ValidationError("End date must be in the future.")
        return value

    def validate_next_payment_date(self, value):
        """Ensure next_payment_date is in the future"""
        from django.utils import timezone

        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "Next payment date must be in the future."
            )
        return value

    def create(self, validated_data):
        """Handle subscription_plan_id during creation"""
        subscription_plan_id = validated_data.pop("subscription_plan_id", None)
        stripe_id = validated_data.pop("stripe_id", None)

        if subscription_plan_id:
            try:
                subscription_plan = SubscriptionPlan.objects.get(
                    subscription_plan_id=subscription_plan_id
                )
                validated_data["subscription_plan"] = subscription_plan
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError(
                    {"subscription_plan_id": "Invalid subscription plan ID."}
                )

        if stripe_id:
            validated_data["stripe_id"] = stripe_id

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle subscription_plan_id during update"""
        subscription_plan_id = validated_data.pop("subscription_plan_id", None)
        stripe_id = validated_data.pop("stripe_id", None)

        if subscription_plan_id is not None:
            try:
                subscription_plan = SubscriptionPlan.objects.get(
                    subscription_plan_id=subscription_plan_id
                )
                validated_data["subscription_plan"] = subscription_plan
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError(
                    {"subscription_plan_id": "Invalid subscription plan ID."}
                )

        if stripe_id is not None:
            validated_data["stripe_id"] = stripe_id

        return super().update(instance, validated_data)


class SubscriptionDetailSerializer(SubscriptionSerializer):
    """
    Detailed subscription serializer that includes stripe_id for admin/internal use.
    Use with caution - only expose to authorized users.
    """

    stripe_id = serializers.CharField(read_only=True, max_length=255)

    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields
        read_only_fields = SubscriptionSerializer.Meta.read_only_fields + ["stripe_id"]


class OrganizationSerializer(serializers.ModelSerializer):
    """
    Serializer for Organization updates.
    Only allows updating organization info, not subscription details.
    """

    organization_id = serializers.UUIDField(read_only=True)
    subscription = SubscriptionSerializer(read_only=True)
    owner_email = serializers.EmailField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "organization_id",
            "business_name",
            "owner_email",
            "subscription",
            "is_active",
            "created_at",
            "updated_at",
            "billing_email",
            "billing_address",
            "contact_number",
            "email_domain",
        ]
        read_only_fields = [
            "organization_id",
            "owner_email",
            "subscription",
            "created_at",
            "updated_at",
        ]

    def validate_business_name(self, value):
        """Validate business name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Business name cannot be empty.")
        return value.strip()

    def validate_billing_email(self, value):
        """Validate billing email format"""
        if value:
            return value.lower().strip()
        return value

    def validate_email_domain(self, value):
        """Validate email domain format."""
        if not value or not value.strip():
            raise serializers.ValidationError("Email domain is required.")
        # Remove @ if present
        domain = value.strip().lstrip("@").lower()
        # Basic validation - should not contain spaces or @
        if " " in domain or "@" in domain:
            raise serializers.ValidationError(
                "Invalid email domain format. Use format like 'company.com'"
            )
        return domain


class OrganizationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing organizations.
    Excludes sensitive billing information.
    """

    organization_id = serializers.UUIDField(read_only=True)
    subscription_plan_name = serializers.CharField(
        source="subscription.subscription_plan.display_name", read_only=True
    )

    class Meta:
        model = Organization
        fields = [
            "organization_id",
            "business_name",
            "is_active",
            "created_at",
            "subscription_plan_name",
        ]
        read_only_fields = [
            "organization_id",
            "created_at",
            "subscription_plan_name",
        ]


class OrganizationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating new organizations with subscription.
    Creates organization, subscription plan, and subscription in one transaction.

    Note: User account creation will be handled in accounts app.
    User details are collected here for owner account creation.
    """

    # Organization fields
    business_name = serializers.CharField(max_length=100)
    owner_email = serializers.EmailField()
    billing_email = serializers.EmailField()
    billing_address = serializers.CharField()
    contact_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    email_domain = serializers.CharField(
        max_length=255,
        help_text="Email domain allowed for signup (e.g., 'company.com')",
    )

    # Owner User Account fields (will be created in accounts app)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)

    # Subscription Plan
    subscription_plan_id = serializers.UUIDField()

    # Subscription fields
    billing_cycle = serializers.ChoiceField(
        choices=[("MONTHLY", "Monthly"), ("YEARLY", "Yearly")]
    )
    end_date = serializers.DateField()
    next_payment_date = serializers.DateField(
        required=False,
        help_text="If not provided, will be calculated based on billing_cycle and current date",
    )
    stripe_id = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_business_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Business name cannot be empty.")
        return value.strip()

    def validate_owner_email(self, value):
        if not value:
            raise serializers.ValidationError("Owner email is required.")
        return value.lower().strip()

    def validate_billing_email(self, value):
        if not value:
            raise serializers.ValidationError("Billing email is required.")
        return value.lower().strip()

    def validate_email_domain(self, value):
        """Validate email domain format."""
        if not value or not value.strip():
            raise serializers.ValidationError("Email domain is required.")
        # Remove @ if present
        domain = value.strip().lstrip("@").lower()
        # Basic validation - should not contain spaces or special chars except dots and hyphens
        if " " in domain or "@" in domain:
            raise serializers.ValidationError(
                "Invalid email domain format. Use format like 'company.com'"
            )
        return domain

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long."
            )
        return value


class DomainSerializer(serializers.ModelSerializer):
    """
    Serializer for Domain model.
    Used for managing tenant domains.
    """

    class Meta:
        model = Domain
        fields = "__all__"
        read_only_fields = ["id"] if hasattr(Domain, "id") else []
