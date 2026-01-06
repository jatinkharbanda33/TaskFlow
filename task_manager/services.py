import logging
from task_manager.models import Task, AuditLog, ScheduledTask
from task_manager.utils.helpers import create_audit_log
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class TaskProcessor:
    @staticmethod
    def process_scheduled_task(scheduled):
        try:
            with transaction.atomic():
                board = scheduled.board

                task = Task.objects.create(
                    title=scheduled.title,
                    description=scheduled.description,
                    status=scheduled.status,
                    priority=scheduled.priority,
                    board=board,
                    created_by=scheduled.created_by,
                    due_date=scheduled.due_date,
                )

                if scheduled.assigned_to.exists():
                    task.assigned_to.set(scheduled.assigned_to.all())

                scheduled.processing_status = ScheduledTask.ProcessingStatus.PROCESSED
                scheduled.failure_reason = None
                scheduled.processed_at = timezone.now()
                scheduled.save()
                create_audit_log(
                    user=scheduled.created_by,
                    action_type=AuditLog.ActionType.TASK_CREATED,
                    description=f"Task '{task.title}' created from scheduled task",
                    metadata={
                        "task_id": str(task.task_id),
                        "scheduled_task_id": str(scheduled.scheduled_task_id),
                        "title": task.title,
                        "board_id": str(board.board_id) if board else None,
                        "board_name": board.name if board else None,
                        "from_scheduled": True,
                    },
                )

            return True, None

        except Exception as e:
            # We can add a retry logic for failed status tasks
            with transaction.atomic():
                scheduled.processing_status = ScheduledTask.ProcessingStatus.FAILED
                scheduled.failure_reason = str(e)
                scheduled.save()

            logger.error(
                f"Failed to process scheduled task {scheduled.scheduled_task_id}: {str(e)}",
                exc_info=True,
            )
            return False, str(e)
