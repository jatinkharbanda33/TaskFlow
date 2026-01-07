"""
Notification service for task-related notifications.
The worker will process queued notification tasks asynchronously.
"""

import logging
from django_q.tasks import async_task

logger = logging.getLogger(__name__)


def send_task_created_notifications(
    task_id: str, task_title: str, assigned_email: str, organization_schema: str
):
    """
    Send notification to assigned user when a task is created.

    This function is designed to be called asynchronously via django-q2.
    It sends email to the assigned user.

    Args:
        task_id: UUID string of the created task
        task_title: Title of the task
        assigned_email: Email address of the assigned user
        organization_schema: Schema name of the organization (tenant)
    """
    try:
        # If no assigned user, skip notifications
        if not assigned_email:
            logger.info(f"No assigned user for task {task_id}, skipping notifications")
            return

        # Prepare notification data
        notification_data = {
            "task_id": task_id,
            "task_title": task_title,
        }

        # Send notification to assigned user
        try:
            _send_notification_to_user(
                user_email=assigned_email,
                notification_data=notification_data,
            )
            logger.info(f"Sent notification for task {task_id} to {assigned_email}")
        except Exception as e:
            logger.error(
                f"Failed to send notification to {assigned_email}: {str(e)}",
                exc_info=True,
            )

    except Exception as e:
        logger.error(
            f"Error sending task notification for task {task_id}: {str(e)}",
            exc_info=True,
        )


def _send_notification_to_user(user_email: str, notification_data: dict):
    """
    Internal function to send a notification to a single user.

    This is where you would integrate with your notification service:
    - Email (SMTP, SendGrid, etc.)
    - Push notifications
    - SMS
    - In-app notifications
    - Webhooks

    Args:
        user_email: Email address of the user
        notification_data: Dictionary containing task information
    """

    # For now, just log the notification
    logger.info(f"Notification sent to {user_email}")


def queue_task_created_notification(
    task_id: str, task_title: str, assigned_email: str, organization_schema: str
):
    """
    Queue a notification task for when a task is created.

    This is the main entry point that should be called from views/services.
    It queues the notification to be processed asynchronously.

    Args:
        task_id: UUID string of the created task
        task_title: Title of the task
        assigned_email: Email address of the assigned user
        organization_schema: Schema name of the organization (tenant)
    """
    try:
        async_task(
            "notifications.services.send_task_created_notifications",
            task_id,
            task_title,
            assigned_email,
            organization_schema,
            task_name=f"notify_task_created_{task_id}",
        )
        logger.debug(f"Queued notification task for task {task_id}")
    except Exception as e:
        logger.error(
            f"Failed to queue notification for task {task_id}: {str(e)}",
            exc_info=True,
        )
