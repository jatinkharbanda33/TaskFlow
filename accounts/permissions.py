from rest_framework import permissions


class IsOrganizationAdminOrOwner(permissions.BasePermission):
    """
    Permission for admin or owner users.
    Allows access to users with is_admin=True or is_org_owner=True.
    Used for viewing resources.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated and is admin or owner."""
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "is_admin", False) or getattr(
            request.user, "is_org_owner", False
        )


