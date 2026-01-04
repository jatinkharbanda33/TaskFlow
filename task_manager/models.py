from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Task(models.Model):
    """
    Task model for managing tasks within a tenant.
    Each task belongs to a user and can be assigned to multiple users.
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
        on_delete=models.CASCADE,
        related_name="created_tasks",
        db_index=True,
        help_text="User who created this task",
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_tasks",
        blank=True,
        help_text="Users assigned to this task",
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
            models.Index(fields=["board", "status", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["priority", "due_date"]),
            models.Index(fields=["created_by", "status"]),
            models.Index(fields=["status", "priority"]),
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


class ScheduledTask(models.Model):
    """
    Scheduled Task model for tasks that need to be created in the future.
    Used by background workers to process scheduled tasks.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    class ProcessingStatus(models.IntegerChoices):
        PENDING = 0, "Pending"
        PROCESSED = 1, "Processed"
        FAILED = 2, "Failed"

    class RecurrencePattern(models.TextChoices):
        ONCE = "ONCE", "Once"
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    scheduled_task_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_index=True
    )

    # Core Fields
    title = models.CharField(
        max_length=255, db_index=True, help_text="Scheduled task title"
    )
    description = models.TextField(help_text="Task description")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Task status",
    )

    # Relationships
    board = models.ForeignKey(
        "Board",
        on_delete=models.CASCADE,
        related_name="scheduled_tasks",
        db_index=True,
        null=True,
        blank=True,
        help_text="Board this scheduled task will create tasks in",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scheduled_tasks",
        db_index=True,
        help_text="User who created this scheduled task",
    )
    assigned_to = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="assigned_scheduled_tasks",
        blank=True,
        help_text="Users who will be assigned to tasks created from this scheduled task",
    )

    # Task Fields (used when creating Task from ScheduledTask)
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
        help_text="Priority for tasks created from this scheduled task",
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Due date for tasks created from this scheduled task",
    )

    # Scheduling
    scheduled_time = models.DateTimeField(
        db_index=True, help_text="When this task should be processed"
    )
    recurrence_pattern = models.CharField(
        max_length=50,
        choices=RecurrencePattern.choices,
        default=RecurrencePattern.ONCE,
        db_index=True,
        help_text="How often this task should recur",
    )

    # Processing
    processing_status = models.IntegerField(
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        db_index=True,
        help_text="Processing status for background worker",
    )
    failure_reason = models.TextField(
        null=True, blank=True, help_text="Reason if processing failed"
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the scheduled task was created",
    )
    processed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the task was processed"
    )

    class Meta:
        ordering = ["scheduled_time", "-created_at"]
        indexes = [
            models.Index(fields=["processing_status", "scheduled_time"]),
            models.Index(fields=["scheduled_time", "processing_status"]),
            models.Index(fields=["created_by", "scheduled_time"]),
            models.Index(fields=["board", "scheduled_time"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.get_processing_status_display()}"


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
        on_delete=models.CASCADE,
        related_name="created_boards",
        db_index=True,
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
        indexes = [
            models.Index(fields=["created_by", "created_at"]),
        ]

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
        SCHEDULED_TASK_CREATED = "SCHEDULED_TASK_CREATED", "Scheduled Task Created"

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
            models.Index(fields=["action_type", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.created_at}"
