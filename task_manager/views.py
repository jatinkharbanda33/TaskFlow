from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import Http404
from .models import Task
from .serializers import UserSerializer, TaskSerializer, ScheduledTaskSerializer


class ExceptionHandlerMixin:
    """Mixin to handle common exceptions following DRY principle."""
    
    @staticmethod
    def handle_generic_exception():
        """Returns a standardized error response for generic exceptions."""
        return Response(
            {"error": "An error occurred. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    @staticmethod
    def handle_not_found():
        """Returns a standardized error response for not found errors."""
        return Response(
            {"error": "Task not found"},
            status=status.HTTP_404_NOT_FOUND
        )


class RegisterView(ExceptionHandlerMixin, APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():
            try:
                serializer.save()
                return Response(
                    {"message": "User created successfully", "user": serializer.data},
                    status=status.HTTP_201_CREATED
                )
            except Exception:
                return self.handle_generic_exception()

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskListView(ExceptionHandlerMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            tasks = Task.objects.all()
            serializer = TaskSerializer(tasks, many=True)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception:
            return self.handle_generic_exception()
            

    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save(created_by=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception:
                return self.handle_generic_exception()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskDetailView(ExceptionHandlerMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        try:
            return Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        try:
            task = self.get_object(pk)
            serializer = TaskSerializer(task)
            return Response(serializer.data)
        except Http404:
            return self.handle_not_found()

    def put(self, request, pk):
        try:
            task = self.get_object(pk)
            serializer = TaskSerializer(task, data=request.data)

            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response(serializer.data)
                except Exception:
                    return self.handle_generic_exception()
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return self.handle_not_found()

    def patch(self, request, pk):
        try:
            task = self.get_object(pk)
            serializer = TaskSerializer(task, data=request.data, partial=True)

            if serializer.is_valid():
                try:
                    serializer.save()
                    return Response(serializer.data)
                except Exception:
                    return self.handle_generic_exception()
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return self.handle_not_found()

    def delete(self, request, pk):
        try:
            task = self.get_object(pk)
            task.delete()
            return Response({"message": "Task deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return self.handle_not_found()


class UserDetailView(ExceptionHandlerMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        try:
            user = request.user
            user.delete()
            return Response(
                {"message": "User account deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception:
            return self.handle_generic_exception()


class ScheduledTaskView(ExceptionHandlerMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ScheduledTaskSerializer(data=request.data)

        if serializer.is_valid():
            try:
                serializer.save(created_by=request.user)
                return Response(
                    {"message": "Task scheduled successfully", "data": serializer.data},
                    status=status.HTTP_201_CREATED
                )
            except Exception:
                return self.handle_generic_exception()

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
