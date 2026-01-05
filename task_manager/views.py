import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Task, Board, ScheduledTask, AuditLog
from .serializers import (
    BoardSerializer,
    BoardListSerializer,
    BoardDetailSerializer,
    TaskSerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    ScheduledTaskSerializer,
    ScheduledTaskListSerializer,
    AuditLogSerializer,
)
from accounts.permissions import IsOrganizationAdminOrOwner
from .utils.helpers import create_audit_log

logger = logging.getLogger(__name__)


class BoardListView(APIView):
    """List all boards. Authenticated users can view."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            boards = Board.objects.all().order_by("name")
            serializer = BoardListSerializer(boards, many=True)
            return Response(
                {"count": boards.count(), "results": serializer.data},
                status=status.HTTP_200_OK,
            )
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
                    # Create audit log
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
                    # Create audit log
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
                # Create audit log
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
            serializer = TaskListSerializer(queryset, many=True)
            return Response(
                {"count": queryset.count(), "results": serializer.data},
                status=status.HTTP_200_OK,
            )
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
                    # Create audit log
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
                    # Create audit log
                    action_type = AuditLog.ActionType.TASK_UPDATED
                    description = f"Task '{updated_task.title}' updated"

                    # Check if status changed to COMPLETED
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
                # Create audit log
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


class ScheduledTaskListView(APIView):
    """List scheduled tasks. Authenticated users can view their own."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Users can only see their own scheduled tasks
            queryset = ScheduledTask.objects.filter(created_by=request.user).order_by(
                "scheduled_time", "-created_at"
            )

            # Filter by processing_status if provided
            processing_status = request.query_params.get("processing_status")
            if processing_status:
                try:
                    processing_status = int(processing_status)
                    valid_statuses = [
                        choice[0] for choice in ScheduledTask.ProcessingStatus.choices
                    ]
                    if processing_status in valid_statuses:
                        queryset = queryset.filter(processing_status=processing_status)
                except ValueError:
                    pass

            serializer = ScheduledTaskListSerializer(queryset, many=True)
            return Response(
                {"count": queryset.count(), "results": serializer.data},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve scheduled tasks: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve scheduled tasks"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ScheduledTaskCreateView(APIView):
    """Create a new scheduled task. Authenticated users can create."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = ScheduledTaskSerializer(
                data=request.data, context={"request": request}
            )
            if serializer.is_valid():
                with transaction.atomic():
                    scheduled_task = serializer.save()
                    # Create audit log
                    create_audit_log(
                        user=request.user,
                        action_type=AuditLog.ActionType.SCHEDULED_TASK_CREATED,
                        description=f"Scheduled task '{scheduled_task.title}' created",
                        request=request,
                        metadata={
                            "scheduled_task_id": str(scheduled_task.scheduled_task_id),
                            "task_title": scheduled_task.title,
                            "scheduled_time": scheduled_task.scheduled_time.isoformat(),
                            "recurrence_pattern": scheduled_task.recurrence_pattern,
                        },
                    )
                response_serializer = ScheduledTaskSerializer(scheduled_task)
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
            logger.error(f"Failed to create scheduled task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create scheduled task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ScheduledTaskDetailView(APIView):
    """Get a scheduled task. Authenticated users can view their own."""

    permission_classes = [IsAuthenticated]

    def get(self, request, scheduled_task_id):
        try:
            scheduled_task = ScheduledTask.objects.get(
                scheduled_task_id=scheduled_task_id
            )

            # Users can only view their own scheduled tasks
            if scheduled_task.created_by != request.user:
                return Response(
                    {"error": "You can only view your own scheduled tasks"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            serializer = ScheduledTaskSerializer(scheduled_task)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ScheduledTask.DoesNotExist:
            return Response(
                {"error": "Scheduled task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve scheduled task: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve scheduled task"},
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
            serializer = AuditLogSerializer(queryset, many=True)
            return Response(
                {"count": queryset.count(), "results": serializer.data},
                status=status.HTTP_200_OK,
            )
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
