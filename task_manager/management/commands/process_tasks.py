from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django_tenants.utils import schema_context
from organizations.models import Organization
from task_manager.models import Task, ScheduledTask


class Command(BaseCommand):
    help = 'Process scheduled tasks that are due to be executed'

    def handle(self, *args, **options):
        now = timezone.now()
        organizations_list = Organization.objects.exclude(schema_name='public')
        
        total_processed = 0
        total_failed = 0
        
        for organization in organizations_list:
            with schema_context(organization.schema_name):
                # Start a Database Transaction
                with transaction.atomic():
                    
                    # --- THE MAGIC FIX ---
                    # select_for_update(): Locks these rows so no one else can write to them.
                    # skip_locked=True: If Cron A has locked these rows, Cron B will 
                    #                 IGNORE them and look for other available rows.
                    due_tasks = ScheduledTask.objects.select_for_update(skip_locked=True).filter(
                        processing_status=0, 
                        scheduled_time__lte=now
                    )
                    
                    # If Cron A locked everything, Cron B sees an empty list here and exits safely.
                    if not due_tasks.exists():
                        continue

                    # ... inside the loop ...
                    for scheduled in due_tasks:
                        from task_manager.services import TaskProcessor
                        success, error_msg = TaskProcessor.process_scheduled_task(scheduled)

                        if success:
                            total_processed += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ Processed: {scheduled.title}'))
                        else:
                            total_failed += 1
                            self.stdout.write(self.style.ERROR(f'✗ Failed: {scheduled.title} - {error_msg}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {total_processed} processed, {total_failed} failed'
            )
        )

