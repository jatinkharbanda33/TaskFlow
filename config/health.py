"""
Health check endpoints for monitoring and load balancer health checks.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Basic health check endpoint.
    Returns 200 if the application is running.
    Used by load balancers for basic health monitoring.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        """Return simple health status."""
        return Response(
            {"status": "healthy", "service": "TaskFlow API"},
            status=status.HTTP_200_OK,
        )

