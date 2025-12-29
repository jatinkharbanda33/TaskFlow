from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import tenant_context
from django_tenants.utils import get_tenant_model
from task_manager.models import ScheduledTask
from datetime import datetime


class Command(BaseCommand):
    help = 'Process scheduled tasks that are due to be executed'

    def handle(self, *args, **options):
        Tenant = get_tenant_model()
        tenants = Tenant.objects.exclude(schema_name='public')
        
        total_processed = 0
        total_failed = 0
        
        for tenant in tenants:
            with tenant_context(tenant):
                # Get all scheduled tasks that:
                # 1. Have processing_status = 0 (Pending)
                # 2. Have scheduled_time <= now
                now = timezone.now()
                due_tasks = ScheduledTask.objects.filter(
                    processing_status=0,  # Pending
                    scheduled_time__lte=now
                )
                
                for task in due_tasks:
                    try:
                        # Process the task: Create a Task from the ScheduledTask
                        from task_manager.models import Task
                        
                        Task.objects.create(
                            title=task.title,
                            description=task.description,
                            status=task.status,  # Use the status from scheduled task
                            created_by=task.created_by
                        )
                        
                        # Mark as processed
                        task.processing_status = 1  # Processed
                        task.failure_reason = None
                        task.save()
                        
                        total_processed += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Processed task "{task.title}" for tenant {tenant.schema_name}'
                            )
                        )
                        
                    except Exception as e:
                        # Mark as failed
                        task.processing_status = 2  # Failed
                        task.failure_reason = str(e)
                        task.save()
                        
                        total_failed += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'✗ Failed to process task "{task.title}" for tenant {tenant.schema_name}: {str(e)}'
                            )
                        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {total_processed} tasks processed, {total_failed} tasks failed'
            )
        )

