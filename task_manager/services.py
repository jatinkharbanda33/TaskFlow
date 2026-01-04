from task_manager.models import Task, Board, AuditLog, ScheduledTask
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class TaskProcessor:
    """
    Sole Responsibility: Knows HOW to process a single scheduled task.
    Does not care about loops, schemas, or cron jobs.
    """

    @staticmethod
    def get_or_create_default_board(user):
        """
        Get or create a default board for the user.
        If user has no boards, create a 'Default Board'.
        Otherwise, use the first board they created.
        """
        try:
            # Try to get user's first board
            board = Board.objects.filter(created_by=user).first()
            if board:
                return board

            # Create default board if none exists
            board = Board.objects.create(
                name="Default Board",
                description="Default board for scheduled tasks",
                created_by=user,
            )
            logger.info(f"Created default board for user {user.email}")
            return board
        except Exception as e:
            logger.error(
                f"Failed to get or create board for user {user.email}: {str(e)}"
            )
            raise

    @staticmethod
    def calculate_next_scheduled_time(scheduled_task):
        """
        Calculate next scheduled time based on recurrence pattern.
        Returns None if pattern is ONCE (no recurrence).
        """
        if scheduled_task.recurrence_pattern == ScheduledTask.RecurrencePattern.ONCE:
            return None

        now = timezone.now()
        if scheduled_task.recurrence_pattern == ScheduledTask.RecurrencePattern.DAILY:
            return now + timedelta(days=1)
        elif (
            scheduled_task.recurrence_pattern == ScheduledTask.RecurrencePattern.WEEKLY
        ):
            return now + timedelta(weeks=1)
        elif (
            scheduled_task.recurrence_pattern == ScheduledTask.RecurrencePattern.MONTHLY
        ):
            # Approximate month as 30 days
            return now + timedelta(days=30)

        return None

    @staticmethod
    def process_scheduled_task(scheduled):
        """
        Process a scheduled task:
        1. Create the actual Task from ScheduledTask
        2. Update ScheduledTask processing status
        3. Handle recurrence if needed
        4. Create audit log
        """
        try:
            with transaction.atomic():
                # 1. Get board (use scheduled board or get/create default for backward compatibility)
                board = scheduled.board
                if not board:
                    # Fallback for old scheduled tasks without board
                    board = Board.objects.filter(
                        created_by=scheduled.created_by
                    ).first()
                    if not board:
                        board = Board.objects.create(
                            name="Default Board",
                            description="Default board for scheduled tasks",
                            created_by=scheduled.created_by,
                        )

                # 2. Create the actual task using fields from scheduled task
                task = Task.objects.create(
                    title=scheduled.title,
                    description=scheduled.description,
                    status=scheduled.status,
                    priority=scheduled.priority,
                    board=board,
                    created_by=scheduled.created_by,
                    due_date=scheduled.due_date,
                )

                # 3. Assign users if any
                if scheduled.assigned_to.exists():
                    task.assigned_to.set(scheduled.assigned_to.all())

                # 4. Update scheduled task status and set processed_at
                scheduled.processing_status = ScheduledTask.ProcessingStatus.PROCESSED
                scheduled.failure_reason = None
                scheduled.processed_at = timezone.now()

                # 5. Handle recurrence - create next scheduled task if needed
                next_scheduled_time = TaskProcessor.calculate_next_scheduled_time(
                    scheduled
                )
                if next_scheduled_time:
                    # Create next occurrence with all fields
                    next_scheduled = ScheduledTask.objects.create(
                        title=scheduled.title,
                        description=scheduled.description,
                        status=scheduled.status,
                        priority=scheduled.priority,
                        board=board,  # Use the board we determined above
                        due_date=scheduled.due_date,
                        scheduled_time=next_scheduled_time,
                        recurrence_pattern=scheduled.recurrence_pattern,
                        created_by=scheduled.created_by,
                        processing_status=ScheduledTask.ProcessingStatus.PENDING,
                    )
                    # Copy assigned users
                    if scheduled.assigned_to.exists():
                        next_scheduled.assigned_to.set(scheduled.assigned_to.all())
                    logger.info(
                        f"Created next occurrence for recurring task: {scheduled.title}"
                    )

                scheduled.save()

                # 5. Create audit log
                try:
                    AuditLog.objects.create(
                        user=scheduled.created_by,
                        action_type=AuditLog.ActionType.TASK_CREATED,
                        description=f"Task '{task.title}' created from scheduled task",
                        metadata={
                            "task_id": str(task.task_id),
                            "scheduled_task_id": str(scheduled.scheduled_task_id),
                            "title": task.title,
                            "board_id": str(board.board_id),
                            "board_name": board.name,
                            "from_scheduled": True,
                        },
                    )
                except Exception as e:
                    logger.error(f"Failed to create audit log: {str(e)}")

            return True, None  # Success, No Error

        except Exception as e:
            # Handle Failure
            try:
                scheduled.processing_status = ScheduledTask.ProcessingStatus.FAILED
                scheduled.failure_reason = str(e)
                scheduled.save()
            except Exception as save_error:
                logger.error(
                    f"Failed to update scheduled task failure status: {str(save_error)}"
                )

            logger.error(
                f"Failed to process scheduled task {scheduled.scheduled_task_id}: {str(e)}"
            )
            return False, str(e)  # Failure, Error Message
