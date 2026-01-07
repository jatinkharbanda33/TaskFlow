from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError
import uuid
from .managers import UserAccountManager


class UserAccount(AbstractBaseUser, PermissionsMixin):
    """
    User account model in shared schema.
    Each user belongs to exactly one organization.
    """

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)

    # Organization relationship - user can only belong to one organization
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="users",
        db_index=True,
        help_text="Organization this user belongs to",
    )

    # Roles & Permissions (scoped to organization)
    is_org_owner = models.BooleanField(
        default=False, help_text="Owner has full access to billing/settings."
    )
    is_admin = models.BooleanField(
        default=False, help_text="Admins can manage other users in the organization."
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into this admin site.",
    )

    # Access Control
    is_active = models.BooleanField(default=True, help_text="True is user left the organization")
    is_restricted = models.BooleanField(default=False, help_text=" True if user is flagged for some illegal activity")

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    objects = UserAccountManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["organization"]

    class Meta:
        indexes = [
            models.Index(fields=["organization", "email"]),
            models.Index(fields=["organization", "is_active"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        """Validate that user belongs to exactly one organization."""
        if not self.organization:
            raise ValidationError("User must belong to an organization.")
