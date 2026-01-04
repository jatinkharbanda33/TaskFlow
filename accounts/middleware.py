from django.utils.deprecation import MiddlewareMixin


class UserOrganizationMiddleware(MiddlewareMixin):
    """
    Simple middleware to add request.organization alias for request.tenant.
    Or to attach other things with request for downstream use

   
    """

    def process_request(self, request):
        
        # django-tenants sets request.tenant, we add request.organization as alias
        request.organization = getattr(request, "tenant", None)
