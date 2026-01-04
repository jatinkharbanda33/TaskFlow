from django.urls import path
from . import views

app_name = "task_manager"

urlpatterns = [
    # Boards
    path("boards/", views.BoardListView.as_view(), name="board-list"),
    path("boards/create/", views.BoardCreateView.as_view(), name="board-create"),
    path(
        "boards/<uuid:board_id>/", views.BoardDetailView.as_view(), name="board-detail"
    ),
    # Tasks
    path("tasks/", views.TaskListView.as_view(), name="task-list"),
    path("tasks/create/", views.TaskCreateView.as_view(), name="task-create"),
    path("tasks/<uuid:task_id>/", views.TaskDetailView.as_view(), name="task-detail"),
    # Scheduled Tasks
    path(
        "scheduled-tasks/",
        views.ScheduledTaskListView.as_view(),
        name="scheduled-task-list",
    ),
    path(
        "scheduled-tasks/create/",
        views.ScheduledTaskCreateView.as_view(),
        name="scheduled-task-create",
    ),
    path(
        "scheduled-tasks/<uuid:scheduled_task_id>/",
        views.ScheduledTaskDetailView.as_view(),
        name="scheduled-task-detail",
    ),
    # Audit Logs (Admin/Owner only)
    path("audit-logs/", views.AuditLogListView.as_view(), name="audit-log-list"),
    path(
        "audit-logs/<uuid:audit_log_id>/",
        views.AuditLogDetailView.as_view(),
        name="audit-log-detail",
    ),
]
