from django.urls import path
from .views import RegisterView, TaskListView, TaskDetailView, UserDetailView, ScheduledTaskView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    path('login', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('user/delete', UserDetailView.as_view(), name='delete-user'),
    path('tasks', TaskListView.as_view(), name='task-list'),
    path('tasks/<pk>', TaskDetailView.as_view(), name='task-detail'),
    path('tasks/schedule/', ScheduledTaskView.as_view(), name='schedule-task'),
]