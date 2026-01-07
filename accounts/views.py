import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from config.pagination import StandardPageNumberPagination
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model

from .serializers import (
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    UserListSerializer,
    UserDetailSerializer,
    CreateUserSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsOrganizationAdminOrOwner

User = get_user_model()
logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    """Login endpoint. Returns access and refresh tokens."""

    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """Logout endpoint. Blacklists refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logged out successfully."}, status=status.HTTP_200_OK
            )
        except (TokenError, InvalidToken):
            return Response(
                {"error": "Token is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to logout: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to logout"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChangePasswordView(APIView):
    """Change password endpoint. User can change their own password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = ChangePasswordSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            user = request.user

            # Verify old password
            if not user.check_password(serializer.validated_data["old_password"]):
                return Response(
                    {"old_password": ["Incorrect password."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update password
            with transaction.atomic():
                user.set_password(serializer.validated_data["new_password"])
                user.save()

            return Response(
                {"message": "Password updated successfully."},
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update password: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update password"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserProfileView(APIView):
    """Get or update own user profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            serializer = UserProfileSerializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to retrieve profile: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        try:
            serializer = UserProfileSerializer(
                request.user, data=request.data, partial=True
            )
            if serializer.is_valid():
                with transaction.atomic():
                    updated_user = serializer.save()
                response_serializer = UserProfileSerializer(updated_user)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update profile: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserListView(APIView):
    """List all users in the organization. Admin/Owner can view."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        try:
            # Get organization from request
            organization = getattr(request, "organization", None)
            if not organization:
                return Response(
                    {"error": "Organization context not available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Filter users by organization
            users = User.objects.filter(organization=organization).order_by(
                "-date_joined"
            )

            # Apply pagination
            paginator = StandardPageNumberPagination()

            paginated_users = paginator.paginate_queryset(users, request)
            serializer = UserListSerializer(paginated_users, many=True)

            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            logger.error(f"Failed to retrieve users: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve users"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserDetailView(APIView):
    """Get or update specific user. Admin/Owner can access any, user can access own."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request, user_id):
        try:
            # Get organization from request
            organization = getattr(request, "organization", None)
            if not organization:
                return Response(
                    {"error": "Organization context not available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get user and ensure they belong to the same organization
            user = User.objects.get(user_id=user_id, organization=organization)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve user: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Check if user can access (admin/owner or self)
        if not (
            request.user.is_org_owner or request.user.is_admin or request.user == user
        ):
            return Response(
                {"error": "You do not have permission to view this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            serializer = UserDetailSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to retrieve user: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, user_id):
        # Only admin/owner can update other users
        if not (request.user.is_org_owner or request.user.is_admin):
            # User can only update themselves
            if request.user.user_id != user_id:
                return Response(
                    {"error": "You can only update your own profile."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            # Get organization from request
            organization = getattr(request, "organization", None)
            if not organization:
                return Response(
                    {"error": "Organization context not available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get user and ensure they belong to the same organization
            user = User.objects.get(user_id=user_id, organization=organization)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve user: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            serializer = UserDetailSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                with transaction.atomic():
                    updated_user = serializer.save()
                response_serializer = UserDetailSerializer(updated_user)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserCreateView(APIView):
    """Signup endpoint. Anyone with matching email domain can signup."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Get organization from request (set by django-tenants middleware)
            organization = getattr(request, "organization", None)
            if not organization:
                return Response(
                    {"error": "Organization context not available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if organization has email_domain set
            if not organization.email_domain:
                return Response(
                    {"error": "Organization does not allow email signups"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = CreateUserSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Validate email domain matches organization's email_domain
            email = serializer.validated_data.get("email", "").lower().strip()
            email_domain = email.split("@")[-1] if "@" in email else ""

            if email_domain != organization.email_domain.lower().strip():
                return Response(
                    {
                        "email": [
                            f"Email domain must match organization domain: {organization.email_domain}"
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if email already exists in database (globally unique)
            if User.objects.filter(email=email).exists():
                return Response(
                    {"email": ["An account already exists with this email."]},
                    status=status.HTTP_409_CONFLICT,
                )

            # Create user with organization
            with transaction.atomic():
                user = serializer.save(organization=organization)

            response_serializer = UserDetailSerializer(user)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {
                    "email": [
                        "A user with this email already exists in this organization."
                    ]
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
