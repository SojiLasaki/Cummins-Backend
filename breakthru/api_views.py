"""
API root and frontend-facing entrypoint.
GET /api/ returns links and auth info so the frontend can discover endpoints.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """
    Public API root. No auth required.
    Frontend can use this to get the base URL and main endpoints.
    """
    # Build absolute base URL (e.g. http://localhost:8000)
    scheme = request.scheme
    host = request.get_host()
    base = f"{scheme}://{host}"
    api_base = f"{base}/api"

    return Response({
        "api_base": f"{api_base}/",
        "auth": {
            "login": f"{api_base}/auth/login/",
            "refresh": f"{api_base}/auth/refresh/",
        },
        "endpoints": {
            "technicians": f"{api_base}/technicians/",
            "tickets": f"{api_base}/tickets/",
            "schedules": f"{api_base}/schedules/",
        },
        "auth_required": "Use JWT: Authorization: Bearer <access_token>",
    })
