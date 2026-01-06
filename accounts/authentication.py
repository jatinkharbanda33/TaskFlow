from rest_framework_simplejwt.authentication import (
    JWTAuthentication as BaseJWTAuthentication,
)
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()


class JWTAuthentication(BaseJWTAuthentication):
    """
    Custom JWT Authentication for shared user accounts.

    1. Look up user in shared schema (public schema)
    2. Validate user belongs to the current organization (from request.tenant)
    3. Check is_restricted status
    """

    def authenticate(self, request):
        """
        Override to get request for organization validation.
        """
        header = self.get_header(request)
        # If auth header not present, we can't authenticate
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        # If auth token not present, we can't authenticate
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        # Validate user belongs to current organization
        tenant = getattr(request, "tenant", None)
        if tenant and user.organization != tenant:
            raise AuthenticationFailed(
                _("User does not belong to this organization."),
                code="organization_mismatch",
            )

        return (user, validated_token)

    def get_user(self, validated_token):
        """
        Override to:
        1. Get user from shared schema (public schema)
        2. Check is_restricted status
        Note: Organization validation is done in authenticate() method
        """
        # Extract user_id from token
        user_id = validated_token.get("user_id")
        if not user_id:
            raise AuthenticationFailed(
                _("Invalid token. No user_id found."), code="invalid_token"
            )

        try:
            # Users are in public schema, so we query directly
            user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed(_("User not found."), code="user_not_found")

        # Check if user is active
        if not user.is_active:
            raise AuthenticationFailed(
                _("User account is disabled."), code="user_inactive"
            )

        # Check if user is restricted
        if user.is_restricted:
            raise AuthenticationFailed(
                _("User access is restricted."), code="user_restricted"
            )

        return user
