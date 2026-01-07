"""
Custom pagination class that uses Django REST Framework settings.
This ensures consistency across all views and eliminates hardcoded values.
"""

from rest_framework.pagination import PageNumberPagination
from django.conf import settings

# Get pagination settings from REST_FRAMEWORK config at module import time
rest_framework_settings = getattr(settings, "REST_FRAMEWORK", {})


class StandardPageNumberPagination(PageNumberPagination):
    """
    Pagination class that reads configuration from REST_FRAMEWORK settings.
    This ensures all views use the same pagination settings defined in settings.py.
    """

    page_size = rest_framework_settings.get("PAGE_SIZE", 20)
    page_size_query_param = rest_framework_settings.get(
        "PAGE_SIZE_QUERY_PARAM", "page_size"
    )
    max_page_size = rest_framework_settings.get("MAX_PAGE_SIZE", 100)
