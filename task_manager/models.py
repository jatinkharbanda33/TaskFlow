from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid6


class User(AbstractUser):
    """
    This User model will exist SEPARATELY in every tenant schema.
    Tenant A's users are physically in a different table than Tenant B's users.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid6.uuid7,
        editable=False
    )
    pass


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ScheduledTask(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'

    PROCESSING_STATUS_CHOICES = (
        (0, 'Pending'),
        (1, 'Processed'),
        (2, 'Failed'),
    )

    title = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    processing_status = models.IntegerField(choices=PROCESSING_STATUS_CHOICES, default=0)
    failure_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.get_processing_status_display()}"