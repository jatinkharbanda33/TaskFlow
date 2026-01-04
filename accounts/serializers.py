from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer that includes user information.
    Checks restricted status and returns user context.
    """

    def validate(self, attrs):
        data = super().validate(attrs)

        # Check restricted status immediately on login
        if self.user.is_restricted:
            raise serializers.ValidationError(
                "Your account is restricted. Please contact admin."
            )

        # Return user context (exclude sensitive fields)
        data["user"] = {
            "user_id": str(self.user.user_id),
            "email": self.user.email,
            "full_name": self.user.full_name,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "is_org_owner": self.user.is_org_owner,
            "is_admin": self.user.is_admin,
        }

        return data


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile (read/update own profile).
    Excludes sensitive fields and read-only fields.
    """

    user_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "user_id",
            "email",
            "full_name",
            "date_joined",
            "last_login",
        ]

    def validate_first_name(self, value):
        """Validate and clean first name."""
        if value:
            return value.strip()
        return value

    def validate_last_name(self, value):
        """Validate and clean last name."""
        if value:
            return value.strip()
        return value


# Alias for backward compatibility
UserSerializer = UserProfileSerializer


class UserListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing users.
    Used by admin/owner to view user list.
    Excludes sensitive information.
    """

    user_id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "email",
            "full_name",
            "first_name",
            "last_name",
            "is_active",
            "is_restricted",
            "is_admin",
            "date_joined",
        ]
        read_only_fields = [
            "user_id",
            "email",
            "full_name",
            "date_joined",
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user serializer for admin/owner.
    Includes more information but still excludes sensitive fields.
    """

    user_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    is_org_owner = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_restricted",
            "is_admin",
            "is_org_owner",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "user_id",
            "email",
            "full_name",
            "is_org_owner",
            "is_superuser",
            "date_joined",
            "last_login",
        ]

    def validate_first_name(self, value):
        """Validate and clean first name."""
        if value:
            return value.strip()
        return value

    def validate_last_name(self, value):
        """Validate and clean last name."""
        if value:
            return value.strip()
        return value


class CreateUserSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users.
    Only admin/owner can create users.
    Password is write-only and not exposed in responses.
    """

    user_id = serializers.UUIDField(read_only=True)
    password = serializers.CharField(
        write_only=True, required=True, min_length=8, style={"input_type": "password"}
    )
    email = serializers.EmailField(required=True)
    is_org_owner = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "email",
            "password",
            "first_name",
            "last_name",
            "is_active",
            "is_restricted",
            "is_admin",
            "is_staff",
            "is_org_owner",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "user_id",
            "is_org_owner",
            "is_superuser",
            "date_joined",
            "last_login",
        ]

    def validate_email(self, value):
        """Normalize and validate email."""
        if not value:
            raise serializers.ValidationError("Email is required.")
        return value.lower().strip()

    def validate_password(self, value):
        """Validate password strength."""
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long."
            )
        return value

    def validate_first_name(self, value):
        """Validate and clean first name."""
        if value:
            return value.strip()
        return value

    def validate_last_name(self, value):
        """Validate and clean last name."""
        if value:
            return value.strip()
        return value

    def create(self, validated_data):
        """Create user with hashed password and organization."""
        password = validated_data.pop("password")
        # Organization is set in the view, not from serializer data
        user = User.objects.create_user(password=password, **validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password.
    All fields are write-only.
    """

    old_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, write_only=True, min_length=8, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        """Validate old password is provided."""
        if not value:
            raise serializers.ValidationError("Old password is required.")
        return value

    def validate_new_password(self, value):
        """Validate new password strength."""
        if len(value) < 8:
            raise serializers.ValidationError(
                "New password must be at least 8 characters long."
            )
        return value

    def validate(self, attrs):
        """Validate old and new passwords are different."""
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from old password."}
            )
        return attrs
