import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from config.pagination import StandardPageNumberPagination
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings

from .models import SubscriptionPlan, Subscription, Organization, Domain
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionPlanListSerializer,
    SubscriptionSerializer,
    OrganizationSerializer,
    OrganizationCreateSerializer,
)
from .permissions import IsOrganizationAdminOrOwner
from .utils.helper import (
    calculate_next_payment_date,
    generate_schema_name,
    generate_domain_name,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class SubscriptionPlanListView(APIView):
    """List all subscription plans. Public endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            plans = SubscriptionPlan.objects.all().order_by("-created_at")

            # Apply pagination
            paginator = StandardPageNumberPagination()

            paginated_plans = paginator.paginate_queryset(plans, request)
            serializer = SubscriptionPlanListSerializer(paginated_plans, many=True)

            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(
                f"Failed to retrieve subscription plans: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve subscription plans"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubscriptionPlanDetailView(APIView):
    """Get specific subscription plan. Public endpoint."""

    permission_classes = [AllowAny]

    def get(self, request, subscription_plan_id):
        try:
            plan = SubscriptionPlan.objects.get(
                subscription_plan_id=subscription_plan_id
            )
            serializer = SubscriptionPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"error": "Subscription plan not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve subscription plan: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve subscription plan"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrganizationCreateView(APIView):
    """Create new organization with subscription. Public endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OrganizationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            with transaction.atomic():
                # Get subscription plan
                try:
                    plan = SubscriptionPlan.objects.get(
                        subscription_plan_id=data["subscription_plan_id"]
                    )
                except SubscriptionPlan.DoesNotExist:
                    return Response(
                        {"error": "Subscription plan not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Calculate next_payment_date if not provided
                next_payment_date = data.get("next_payment_date")
                if not next_payment_date:
                    next_payment_date = calculate_next_payment_date(
                        billing_cycle=data["billing_cycle"]
                    )

                # Create subscription
                subscription = Subscription.objects.create(
                    subscription_plan=plan,
                    billing_cycle=data["billing_cycle"],
                    end_date=data["end_date"],
                    next_payment_date=next_payment_date,
                    stripe_id=data.get("stripe_id", ""),
                    is_active=True,
                )

                # Generate schema name and domain for the organization
                schema_name = generate_schema_name(data["business_name"])
                domain_name = generate_domain_name(
                    data["business_name"], settings.BASE_DOMAIN
                )

                organization = Organization.objects.create(
                    business_name=data["business_name"],
                    owner_email=data["owner_email"],
                    billing_email=data["billing_email"],
                    billing_address=data["billing_address"],
                    contact_number=data.get("contact_number", ""),
                    email_domain=data["email_domain"].lower().strip(),
                    subscription=subscription,
                    schema_name=schema_name,
                    is_active=True,
                )

                Domain.objects.create(
                    domain=domain_name,
                    tenant=organization,
                    is_primary=True,
                )

                owner_email = data["owner_email"].lower().strip()
                try:
                    User.objects.create_user(
                        email=owner_email,
                        password=data["password"],
                        first_name=data.get("first_name", "").strip(),
                        last_name=data.get("last_name", "").strip(),
                        organization=organization,
                        is_org_owner=True,
                        is_staff=True,
                        is_active=True,
                    )
                except IntegrityError:
                    return Response(
                        {
                            "error": "User account creation failed",
                            "detail": "An account with this email already exists.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            response_serializer = OrganizationSerializer(organization)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {
                    "error": "Failed to create organization",
                    "detail": "A user or organization with this information already exists.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Failed to create organization: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create organization"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrganizationDetailView(APIView):
    """Get or update organization info. Admin/Owner can view, Owner can update."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        try:
            organization = request.organization
            if not organization:
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = OrganizationSerializer(organization)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except AttributeError:
            return Response(
                {"error": "Organization context not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve organization: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve organization"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        # Only owner can update
        if not getattr(request.user, "is_org_owner", False):
            return Response(
                {"error": "Only organization owner can update organization details"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            organization = request.organization
            if not organization:
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = OrganizationSerializer(
                organization, data=request.data, partial=True
            )
            if serializer.is_valid():
                with transaction.atomic():
                    updated_organization = serializer.save()
                response_serializer = OrganizationSerializer(updated_organization)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except AttributeError:
            return Response(
                {"error": "Organization context not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update organization: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update organization"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrganizationSubscriptionView(APIView):
    """Manage organization subscription. Owner can cancel or update stripe_id."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        """Get current subscription details."""
        try:
            organization = request.organization
            if not organization or not organization.subscription:
                return Response(
                    {"error": "No subscription found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = SubscriptionSerializer(organization.subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except AttributeError:
            return Response(
                {"error": "Organization context not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve subscription: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve subscription"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        """Update stripe_id or cancel subscription. Owner only."""
        if not getattr(request.user, "is_org_owner", False):
            return Response(
                {"error": "Only organization owner can manage subscription"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            organization = request.organization
            if not organization or not organization.subscription:
                return Response(
                    {"error": "No subscription found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            subscription = organization.subscription
            action = request.data.get("action")
            stripe_id = request.data.get("stripe_id")

            with transaction.atomic():
                if action == "cancel":
                    subscription.is_active = False
                    subscription.expired_at = timezone.now()
                    subscription.save()
                    return Response(
                        {"message": "Subscription cancelled successfully"},
                        status=status.HTTP_200_OK,
                    )

                elif action == "update_stripe_id":
                    if not stripe_id:
                        return Response(
                            {"error": "Provide'stripe_id'"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    subscription.stripe_id = stripe_id
                    subscription.save()
                    serializer = SubscriptionSerializer(subscription)
                    return Response(
                        {
                            "message": "Stripe ID updated successfully",
                            "data": serializer.data,
                        },
                        status=status.HTTP_200_OK,
                    )

                else:
                    return Response(
                        {"error": "Provide action: cancel' or 'update_stripe_id'"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        except AttributeError:
            return Response(
                {"error": "Organization context not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update subscription: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update subscription"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrganizationSubscriptionStatusView(APIView):
    """Get organization subscription status. Admin/Owner can view."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        try:
            organization = request.organization
            if not organization:
                return Response(
                    {"error": "Organization not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            subscription_data = None

            if organization.subscription:
                subscription_serializer = SubscriptionSerializer(
                    organization.subscription
                )
                subscription_data = subscription_serializer.data

            return Response(
                {
                    "organization_id": str(organization.organization_id),
                    "business_name": organization.business_name,
                    "is_active": organization.is_active,
                    "subscription": subscription_data,
                },
                status=status.HTTP_200_OK,
            )
        except AttributeError:
            return Response(
                {"error": "Organization context not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve subscription status: {str(e)}", exc_info=True
            )
            return Response(
                {"error": "Failed to retrieve subscription status"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
