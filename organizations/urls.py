from django.urls import path
from . import views

app_name = "organizations"

urlpatterns = [
    # Subscription Plans (Public)
    path(
        "subscription-plans/",
        views.SubscriptionPlanListView.as_view(),
        name="subscription-plan-list",
    ),
    path(
        "subscription-plans/<uuid:subscription_plan_id>/",
        views.SubscriptionPlanDetailView.as_view(),
        name="subscription-plan-detail",
    ),
    # Organization
    path(
        "create/",
        views.OrganizationCreateView.as_view(),
        name="organization-create",
    ),
    path(
        "update/",
        views.OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "subscription/",
        views.OrganizationSubscriptionView.as_view(),
        name="organization-subscription",
    ),
    path(
        "subscription-status/",
        views.OrganizationSubscriptionStatusView.as_view(),
        name="organization-subscription-status",
    ),
]
