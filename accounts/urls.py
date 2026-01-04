from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = "accounts"

urlpatterns = [
    # Authentication
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path(
        "auth/change-password/",
        views.ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    # User Profile
    path("users/me/", views.UserProfileView.as_view(), name="user-profile"),
    # User Management
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<uuid:user_id>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/create/", views.UserCreateView.as_view(), name="user-create"),
]
