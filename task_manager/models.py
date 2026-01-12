from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Task(models.Model):
    """
    Task model for managing tasks within a tenant.
    Each task belongs to a user and can be assigned to one user.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        ON_HOLD = "ON_HOLD", "On Hold"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    task_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    # Core Fields
    title = models.CharField(max_length=255, db_index=True, help_text="Task title")
    description = models.TextField(blank=True, help_text="Detailed task description")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current status of the task",
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
        help_text="Task priority level",
    )

    # Relationships
    board = models.ForeignKey(
        "Board",
        on_delete=models.CASCADE,
        related_name="tasks",
        db_index=True,
        help_text="Board this task belongs to",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
        null=True,
        db_index=True,
        help_text="User who created this task",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        db_index=True,
        help_text="User assigned to this task",
    )

    # Dates
    due_date = models.DateTimeField(
        null=True, blank=True, db_index=True, help_text="Task due date and time"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the task was completed"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When the task was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the task was last updated"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["board", "status", "-created_at"]
            ),  # for checking tasks in board with filters
            models.Index(fields=["priority", "due_date"]),
            models.Index(
                fields=["created_by", "status"]
            ),  # for user to check the tasks they have created
            models.Index(fields=["status", "priority"]),
            models.Index(
                fields=["assigned_to", "status", "priority"]
            ),  # For user to check their own tasks
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-set completed_at when status changes to COMPLETED."""
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != self.Status.COMPLETED:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if task is overdue."""
        if self.due_date and self.status not in [
            self.Status.COMPLETED,
            self.Status.CANCELLED,
        ]:
            return timezone.now() > self.due_date
        return False


class Board(models.Model):
    """
    Board model for organizing tasks within a tenant.
    Each task belongs to a board.
    """

    board_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    # Core Fields
    name = models.CharField(max_length=100, db_index=True, help_text="Board name")
    description = models.TextField(blank=True, help_text="Board description")

    # Relationships
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_boards",
        help_text="User who created this board",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When the board was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the board was last updated"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """
    Audit log model for tracking important actions.
    Provides an audit trail for compliance and debugging.
    """

    class ActionType(models.TextChoices):
        TASK_CREATED = "TASK_CREATED", "Task Created"
        TASK_UPDATED = "TASK_UPDATED", "Task Updated"
        TASK_DELETED = "TASK_DELETED", "Task Deleted"
        TASK_ASSIGNED = "TASK_ASSIGNED", "Task Assigned"
        TASK_COMPLETED = "TASK_COMPLETED", "Task Completed"
        BOARD_CREATED = "BOARD_CREATED", "Board Created"
        BOARD_UPDATED = "BOARD_UPDATED", "Board Updated"
        BOARD_DELETED = "BOARD_DELETED", "Board Deleted"

    audit_log_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=True,
        help_text="User who performed the action",
    )

    # Action Details
    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        db_index=True,
        help_text="Type of action performed",
    )
    description = models.TextField(help_text="Detailed description of the action")
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional metadata about the action"
    )

    # Request Information
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=255, blank=True, help_text="User agent of the request"
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When the action occurred"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "-created_at"]),  # For filtering
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.created_at}"


class DailyStats(models.Model):
    """
    Daily aggregated statistics for each organization.
    Stores pre-calculated metrics to enable fast analytics and reporting.
    """

    daily_stats_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    date = models.DateField(
        db_index=True, help_text="Date for which stats are aggregated"
    )

    tasks_created = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Daily Stats - {self.date}"


class TaskAttachment(models.Model):

    attachment_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    task = models.ForeignKey(
        "Task",
        on_delete=models.CASCADE,
        related_name="attachments",
        db_index=True,
        help_text="Task this attachment belongs to",
    )

    # File metadata
    file_name = models.CharField(max_length=255, help_text="Original filename")
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100, help_text="MIME type")

    # S3 storage info
    s3_key = models.CharField(
        max_length=1024, unique=True, help_text="S3 object key/path"
    )

    # Upload metadata
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_attachments",
        help_text="User who uploaded this file",
    )

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When attachment was created"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.file_name} - {self.task.title}"
