"""
Helper functions for task_manager app.
"""

import logging
from django.db.models import F
from django.utils import timezone
from ..models import AuditLog, DailyStats

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Extract client IP address from request.
    Handles proxy headers (X-Forwarded-For).

    Args:
        request: Django request object

    Returns:
        str: Client IP address or None
    """
    if not request:
        return None

    # Check for forwarded IP (when behind proxy/load balancer)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")

    return ip if ip else None


def get_user_agent(request):
    """
    Extract user agent from request.

    Args:
        request: Django request object

    Returns:
        str: User agent string or empty string
    """
    if not request:
        return ""

    user_agent = request.META.get("HTTP_USER_AGENT", "")
    # Truncate to max length (255 chars)
    return user_agent[:255] if user_agent else ""


def create_audit_log(user, action_type, description, request=None, metadata=None):
    """
    Create an audit log entry for an action.

    This function safely creates audit logs and handles errors gracefully.
    Audit logging should never break the main operation.

    Args:
        user: User who performed the action
        action_type: ActionType enum value (e.g., AuditLog.ActionType.TASK_CREATED)
        description: Human-readable description of the action
        request: Django request object (optional, for IP and user agent)
        metadata: Optional dict with additional context

    Returns:
        AuditLog: Created audit log instance, or None if creation failed
    """
    try:
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        audit_log = AuditLog.objects.create(
            user=user,
            action_type=action_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )

        return audit_log
    except Exception as e:
        # Log the error but don't raise - audit logging should never break operations
        logger.error(
            f"Failed to create audit log: {str(e)} | "
            f"Action: {action_type} | User: {user}",
            exc_info=True,
        )
        return None


def increment_daily_stat(stat_field):
    """
    Atomically increment a daily statistics counter for today.

    This function safely updates daily stats and handles errors gracefully.
    Stats updates should never break the main operation.

    Args:
        stat_field: Field name to increment (e.g., 'tasks_created', 'tasks_updated')

    Returns:
        None (fails silently on error)
    """
    try:
        today = timezone.now().date()
        DailyStats.objects.update_or_create(date=today, defaults={stat_field: 0})
        DailyStats.objects.filter(date=today).update(**{stat_field: F(stat_field) + 1})
    except Exception as e:
        logger.error(
            f"Failed to increment daily stat '{stat_field}': {str(e)}",
            exc_info=True,
        )
