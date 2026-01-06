from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Task, Board, ScheduledTask, AuditLog, DailyStats

User = get_user_model()


class BoardListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing boards.
    Excludes internal fields and relationships.
    """

    board_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Board
        fields = [
            "board_id",
            "name",
            "description",
            "created_at",
        ]
        read_only_fields = ["board_id", "created_at"]


class BoardSerializer(serializers.ModelSerializer):
    """
    Serializer for Board model.
    Used for creating and updating boards.
    """

    board_id = serializers.UUIDField(read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Board
        fields = [
            "board_id",
            "name",
            "description",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "board_id",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        """Validate and clean board name."""
        if not value or not value.strip():
            raise serializers.ValidationError("Board name cannot be empty.")
        return value.strip()

    def validate_description(self, value):
        """Validate and clean description."""
        if value:
            return value.strip()
        return value


class BoardDetailSerializer(BoardSerializer):
    """
    Detailed board serializer.
    Includes task count and other computed fields.
    """

    task_count = serializers.SerializerMethodField()

    class Meta(BoardSerializer.Meta):
        fields = BoardSerializer.Meta.fields + ["task_count"]

    def get_task_count(self, obj):
        """Get the number of tasks in this board."""
        return obj.tasks.count()


class TaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing tasks.
    Excludes detailed information for performance.
    """

    task_id = serializers.UUIDField(read_only=True)
    board_name = serializers.CharField(source="board.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "task_id",
            "title",
            "status",
            "priority",
            "board_name",
            "created_by_name",
            "due_date",
            "is_overdue",
            "created_at",
        ]
        read_only_fields = [
            "task_id",
            "board_name",
            "created_by_name",
            "is_overdue",
            "created_at",
        ]


class TaskSerializer(serializers.ModelSerializer):
    """
    Serializer for Task model.
    Used for creating and updating tasks.
    """

    task_id = serializers.UUIDField(read_only=True)
    board_id = serializers.UUIDField(write_only=True)
    board_name = serializers.CharField(source="board.name", read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source="assigned_to",
    )
    assigned_to_names = serializers.SerializerMethodField()
    completed_at = serializers.DateTimeField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "task_id",
            "title",
            "description",
            "status",
            "priority",
            "board_id",
            "board_name",
            "created_by",
            "created_by_name",
            "assigned_to_ids",
            "assigned_to_names",
            "due_date",
            "completed_at",
            "is_overdue",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "task_id",
            "board_name",
            "created_by",
            "created_by_name",
            "assigned_to_names",
            "completed_at",
            "is_overdue",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        """Validate and clean task title."""
        if not value or not value.strip():
            raise serializers.ValidationError("Task title cannot be empty.")
        return value.strip()

    def validate_description(self, value):
        """Validate and clean description."""
        if value:
            return value.strip()
        return value

    def validate_status(self, value):
        """Validate status choice."""
        valid_statuses = [choice[0] for choice in Task.Status.choices]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(valid_statuses)}"
            )
        return value

    def validate_priority(self, value):
        """Validate priority choice."""
        valid_priorities = [choice[0] for choice in Task.Priority.choices]
        if value not in valid_priorities:
            raise serializers.ValidationError(
                f"Priority must be one of: {', '.join(valid_priorities)}"
            )
        return value

    def validate_board_id(self, value):
        """Validate board exists."""
        try:
            Board.objects.get(board_id=value)
        except Board.DoesNotExist:
            raise serializers.ValidationError("Board not found.")
        return value

    def validate_due_date(self, value):
        """Validate due date is in the future if provided."""
        if value:
            from django.utils import timezone

            if value <= timezone.now():
                raise serializers.ValidationError("Due date must be in the future.")
        return value

    def create(self, validated_data):
        """Create task with board relationship."""
        board_id = validated_data.pop("board_id")
        try:
            board = Board.objects.get(board_id=board_id)
        except Board.DoesNotExist:
            raise serializers.ValidationError({"board_id": "Board not found."})

        # Set created_by from request user
        validated_data["created_by"] = self.context["request"].user
        validated_data["board"] = board

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update task, handling board_id if provided."""
        board_id = validated_data.pop("board_id", None)
        if board_id:
            try:
                board = Board.objects.get(board_id=board_id)
                validated_data["board"] = board
            except Board.DoesNotExist:
                raise serializers.ValidationError({"board_id": "Board not found."})

        return super().update(instance, validated_data)

    def get_assigned_to_names(self, obj):
        """Get names of assigned users."""
        return [user.full_name for user in obj.assigned_to.all()]


class TaskDetailSerializer(TaskSerializer):
    """
    Detailed task serializer.
    Includes all fields and computed properties.
    """

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields


class ScheduledTaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing scheduled tasks.
    """

    scheduled_task_id = serializers.UUIDField(read_only=True)
    board_name = serializers.CharField(source="board.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )

    class Meta:
        model = ScheduledTask
        fields = [
            "scheduled_task_id",
            "title",
            "status",
            "board_name",
            "priority",
            "scheduled_time",
            "processing_status",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = [
            "scheduled_task_id",
            "board_name",
            "created_by_name",
            "created_at",
        ]


class ScheduledTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for ScheduledTask model.
    Used for creating and updating scheduled tasks.
    """

    scheduled_task_id = serializers.UUIDField(read_only=True)
    board_id = serializers.UUIDField(write_only=True)
    board_name = serializers.CharField(source="board.name", read_only=True)
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=False,
        source="assigned_to",
    )
    assigned_to_names = serializers.SerializerMethodField()
    processing_status = serializers.IntegerField(read_only=True)
    failure_reason = serializers.CharField(read_only=True)
    processed_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ScheduledTask
        fields = [
            "scheduled_task_id",
            "title",
            "description",
            "status",
            "board_id",
            "board_name",
            "priority",
            "due_date",
            "assigned_to_ids",
            "assigned_to_names",
            "scheduled_time",
            "recurrence_pattern",
            "processing_status",
            "failure_reason",
            "processed_at",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = [
            "scheduled_task_id",
            "board_name",
            "assigned_to_names",
            "created_by",
            "created_by_name",
            "processing_status",
            "failure_reason",
            "processed_at",
            "created_at",
        ]

    def validate_title(self, value):
        """Validate and clean title."""
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()

    def validate_description(self, value):
        """Validate and clean description."""
        if not value or not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

    def validate_status(self, value):
        """Validate status choice."""
        valid_statuses = [choice[0] for choice in ScheduledTask.Status.choices]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(valid_statuses)}"
            )
        return value

    def validate_recurrence_pattern(self, value):
        """Validate recurrence pattern choice."""
        valid_patterns = [
            choice[0] for choice in ScheduledTask.RecurrencePattern.choices
        ]
        if value not in valid_patterns:
            raise serializers.ValidationError(
                f"Recurrence pattern must be one of: {', '.join(valid_patterns)}"
            )
        return value

    def validate_scheduled_time(self, value):
        """Validate scheduled time is in the future."""
        from django.utils import timezone

        if value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value

    def validate_priority(self, value):
        """Validate priority choice."""
        valid_priorities = [choice[0] for choice in ScheduledTask.Priority.choices]
        if value not in valid_priorities:
            raise serializers.ValidationError(
                f"Priority must be one of: {', '.join(valid_priorities)}"
            )
        return value

    def validate_board_id(self, value):
        """Validate board exists."""
        try:
            Board.objects.get(board_id=value)
        except Board.DoesNotExist:
            raise serializers.ValidationError("Board not found.")
        return value

    def validate_due_date(self, value):
        """Validate due date is in the future if provided."""
        if value:
            from django.utils import timezone

            if value <= timezone.now():
                raise serializers.ValidationError("Due date must be in the future.")
        return value

    def get_assigned_to_names(self, obj):
        """Get names of assigned users."""
        return [user.full_name for user in obj.assigned_to.all()]

    def create(self, validated_data):
        """Create scheduled task with board and created_by from request user."""
        board_id = validated_data.pop("board_id")
        try:
            board = Board.objects.get(board_id=board_id)
        except Board.DoesNotExist:
            raise serializers.ValidationError({"board_id": "Board not found."})

        validated_data["board"] = board
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AuditLog model.
    Read-only serializer for viewing audit logs.
    """

    audit_log_id = serializers.UUIDField(read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "audit_log_id",
            "user",
            "user_name",
            "action_type",
            "description",
            "metadata",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = [
            "audit_log_id",
            "user",
            "user_name",
            "action_type",
            "description",
            "metadata",
            "ip_address",
            "user_agent",
            "created_at",
        ]


class DailyStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStats
        fields = [
            "daily_stats_id",
            "date",
            "tasks_created",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "daily_stats_id",
            "created_at",
            "updated_at",
        ]
