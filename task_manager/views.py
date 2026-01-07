import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from config.pagination import StandardPageNumberPagination
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Task, Board, AuditLog, DailyStats
from .serializers import (
    BoardSerializer,
    BoardListSerializer,
    BoardDetailSerializer,
    TaskSerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    AuditLogSerializer,
    DailyStatsSerializer,
)
from accounts.permissions import IsOrganizationAdminOrOwner
from .utils.helpers import create_audit_log, increment_daily_stat
from notifications.services import queue_task_created_notification

logger = logging.getLogger(__name__)


class BoardListView(APIView):
    """List all boards. Authenticated users can view."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            boards = Board.objects.all()

            # Search by name if provided
            name = request.query_params.get("name", "").strip()
            if name:
                boards = boards.filter(name__icontains=name)

            # Order by name
            boards = boards.order_by("name")

            # Apply pagination
            paginator = StandardPageNumberPagination()

            paginated_boards = paginator.paginate_queryset(boards, request)
            serializer = BoardListSerializer(paginated_boards, many=True)

            return paginator.get_paginated_response(serializer.data)
        except NotFound:
            # Invalid page number - return 404
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve boards: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve boards"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BoardCreateView(APIView):
    """Create a new board. Authenticated users can create."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = BoardSerializer(data=request.data)
            if serializer.is_valid():
                with transaction.atomic():
                    board = serializer.save(created_by=request.user)
                    create_audit_log(
                        user=request.user,
                        action_type=AuditLog.ActionType.BOARD_CREATED,
                        description=f"Board '{board.name}' created",
                        request=request,
                        metadata={
                            "board_id": str(board.board_id),
                            "board_name": board.name,
                        },
                    )
                response_serializer = BoardDetailSerializer(board)
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to create board: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create board"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BoardDetailView(APIView):
    """Get, update, or delete a board. Authenticated users can view, creator can update/delete."""

    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        try:
            board = Board.objects.get(board_id=board_id)
            serializer = BoardDetailSerializer(board)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Board.DoesNotExist:
            return Response(
                {"error": "Board not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve board: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve board"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, board_id):
        try:
            board = Board.objects.get(board_id=board_id)
        except Board.DoesNotExist:
            return Response(
                {"error": "Board not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Only creator can update
        if board.created_by != request.user:
            return Response(
                {"error": "You can only update boards you created"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            serializer = BoardSerializer(board, data=request.data, partial=True)
            if serializer.is_valid():
                with transaction.atomic():
                    updated_board = serializer.save()
                    create_audit_log(
                        user=request.user,
                        action_type=AuditLog.ActionType.BOARD_UPDATED,
                        description=f"Board '{updated_board.name}' updated",
                        request=request,
                        metadata={
                            "board_id": str(updated_board.board_id),
                            "board_name": updated_board.name,
                        },
                    )
                response_serializer = BoardDetailSerializer(updated_board)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update board: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update board"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, board_id):
        try:
            board = Board.objects.get(board_id=board_id)
        except Board.DoesNotExist:
            return Response(
                {"error": "Board not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Only creator can delete
        if board.created_by != request.user:
            return Response(
                {"error": "You can only delete boards you created"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            board_name = board.name
            board_id = str(board.board_id)
            with transaction.atomic():
                board.delete()
                create_audit_log(
                    user=request.user,
                    action_type=AuditLog.ActionType.BOARD_DELETED,
                    description=f"Board '{board_name}' deleted",
                    request=request,
                    metadata={"board_id": board_id, "board_name": board_name},
                )
            return Response(
                {"message": "Board deleted successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to delete board: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to delete board"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TaskListView(APIView):
    """List tasks. Can filter by board. Authenticated users can view."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            queryset = Task.objects.all()

            # Filter by board if provided
            board_id = request.query_params.get("board_id")
            if board_id:
                try:
                    board = Board.objects.get(board_id=board_id)
                    queryset = queryset.filter(board=board)
                except Board.DoesNotExist:
                    return Response(
                        {"error": "Board not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Search by title if provided
            title = request.query_params.get("title", "").strip()
            if title:
                queryset = queryset.filter(title__icontains=title)

            # Filter by status if provided
            status_filter = request.query_params.get("status")
            if status_filter:
                valid_statuses = [choice[0] for choice in Task.Status.choices]
                if status_filter in valid_statuses:
                    queryset = queryset.filter(status=status_filter)

            # Filter by priority if provided
            priority_filter = request.query_params.get("priority")
            if priority_filter:
                valid_priorities = [choice[0] for choice in Task.Priority.choices]
                if priority_filter in valid_priorities:
                    queryset = queryset.filter(priority=priority_filter)

            queryset = queryset.order_by("-created_at")

            # Apply pagination
            paginator = StandardPageNumberPagination()

            paginated_tasks = paginator.paginate_queryset(queryset, request)
            serializer = TaskListSerializer(paginated_tasks, many=True)

            return paginator.get_paginated_response(serializer.data)
        except NotFound:
            # Invalid page number - return 404
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve tasks: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve tasks"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TaskCreateView(APIView):
    """Create a new task. Authenticated users can create."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = TaskSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                with transaction.atomic():
                    task = serializer.save()
                    create_audit_log(
                        user=request.user,
                        action_type=AuditLog.ActionType.TASK_CREATED,
                        description=f"Task '{task.title}' created in board '{task.board.name}'",
                        request=request,
                        metadata={
                            "task_id": str(task.task_id),
                            "task_title": task.title,
                            "board_id": str(task.board.board_id),
                            "board_name": task.board.name,
                            "status": task.status,
                            "priority": task.priority,
                        },
                    )
                    increment_daily_stat("tasks_created")

                # Queue notification to assigned user if exists
                organization = getattr(request, "tenant", None)
                if organization and task.assigned_to:
                    queue_task_created_notification(
                        task_id=str(task.task_id),
                        task_title=task.title,
                        assigned_email=task.assigned_to.email,
                        organization_schema=organization.schema_name,
                    )

                response_serializer = TaskDetailSerializer(task)
                return Response(
                    response_serializer.data, status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to create task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TaskDetailView(APIView):
    """Get, update, or delete a task. Authenticated users can view, creator can update/delete."""

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        try:
            task = Task.objects.get(task_id=task_id)
            serializer = TaskDetailSerializer(task)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, task_id):
        try:
            task = Task.objects.get(task_id=task_id)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Only creator can update
        if task.created_by != request.user:
            return Response(
                {"error": "You can only update tasks you created"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            old_status = task.status
            serializer = TaskSerializer(
                task, data=request.data, partial=True, context={"request": request}
            )
            if serializer.is_valid():
                with transaction.atomic():
                    updated_task = serializer.save()
                    action_type = AuditLog.ActionType.TASK_UPDATED
                    description = f"Task '{updated_task.title}' updated"

                    if (
                        updated_task.status == Task.Status.COMPLETED
                        and old_status != Task.Status.COMPLETED
                    ):
                        action_type = AuditLog.ActionType.TASK_COMPLETED
                        description = f"Task '{updated_task.title}' completed"

                    create_audit_log(
                        user=request.user,
                        action_type=action_type,
                        description=description,
                        request=request,
                        metadata={
                            "task_id": str(updated_task.task_id),
                            "task_title": updated_task.title,
                            "board_id": str(updated_task.board.board_id),
                            "old_status": old_status,
                            "new_status": updated_task.status,
                            "priority": updated_task.priority,
                        },
                    )
                response_serializer = TaskDetailSerializer(updated_task)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to update task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, task_id):
        try:
            task = Task.objects.get(task_id=task_id)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Only creator can delete
        if task.created_by != request.user:
            return Response(
                {"error": "You can only delete tasks you created"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            task_title = task.title
            task_id = str(task.task_id)
            board_name = task.board.name
            board_id = str(task.board.board_id)
            with transaction.atomic():
                task.delete()
                create_audit_log(
                    user=request.user,
                    action_type=AuditLog.ActionType.TASK_DELETED,
                    description=f"Task '{task_title}' deleted from board '{board_name}'",
                    request=request,
                    metadata={
                        "task_id": task_id,
                        "task_title": task_title,
                        "board_id": board_id,
                        "board_name": board_name,
                    },
                )
            return Response(
                {"message": "Task deleted successfully"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to delete task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to delete task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuditLogListView(APIView):
    """List audit logs. Admin/Owner only."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        try:
            queryset = AuditLog.objects.all()

            # Filter by action_type if provided
            action_type = request.query_params.get("action_type")
            if action_type:
                valid_types = [choice[0] for choice in AuditLog.ActionType.choices]
                if action_type in valid_types:
                    queryset = queryset.filter(action_type=action_type)

            # Filter by user if provided
            user_id = request.query_params.get("user_id")
            if user_id:
                queryset = queryset.filter(user_id=user_id)

            queryset = queryset.order_by("-created_at")

            # Apply pagination
            paginator = StandardPageNumberPagination()

            paginated_logs = paginator.paginate_queryset(queryset, request)
            serializer = AuditLogSerializer(paginated_logs, many=True)

            return paginator.get_paginated_response(serializer.data)
        except NotFound:
            # Invalid page number - return 404
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve audit logs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuditLogDetailView(APIView):
    """Get a specific audit log. Admin/Owner only."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request, audit_log_id):
        try:
            audit_log = AuditLog.objects.get(audit_log_id=audit_log_id)
            serializer = AuditLogSerializer(audit_log)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except AuditLog.DoesNotExist:
            return Response(
                {"error": "Audit log not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve audit log: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve audit log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DailyStatsView(APIView):
    """Get daily statistics for a specific date. Admin/Owner only."""

    permission_classes = [IsAuthenticated, IsOrganizationAdminOrOwner]

    def get(self, request):
        from datetime import datetime

        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"error": "Date parameter is required (format: YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stats = DailyStats.objects.filter(date=target_date).first()
            if not stats:
                stats = DailyStats.objects.create(
                    date=target_date,
                    tasks_created=0,
                )

            serializer = DailyStatsSerializer(stats)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to retrieve daily stats: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve daily stats"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
