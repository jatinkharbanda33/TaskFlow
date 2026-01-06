import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django_tenants.utils import schema_context
from organizations.models import Organization
from task_manager.models import ScheduledTask
from task_manager.services import TaskProcessor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process scheduled tasks that are due to be executed"

    def handle(self, *args, **options):
        now = timezone.now()
        organizations = Organization.objects.exclude(schema_name="public")
        total_processed = 0
        total_failed = 0

        for organization in organizations:
            with schema_context(organization.schema_name):
                with transaction.atomic():
                    due_tasks = ScheduledTask.objects.select_for_update(
                        skip_locked=True
                    ).filter(processing_status=0, scheduled_time__lte=now)

                    if not due_tasks.exists():
                        continue

                    for scheduled in due_tasks:
                        success, error_msg = TaskProcessor.process_scheduled_task(
                            scheduled
                        )
                        if success:
                            total_processed += 1
                        else:
                            total_failed += 1
                            logger.error(
                                f"Failed to process scheduled task {scheduled.scheduled_task_id}: {error_msg}"
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {total_processed} processed, {total_failed} failed"
            )
        )
