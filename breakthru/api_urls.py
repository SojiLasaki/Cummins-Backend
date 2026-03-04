"""
Central API URL config. Mount at "api/" so GET /api/ returns the API root.
"""
from django.urls import path, include

from .api_views import api_root

urlpatterns = [
    path("", api_root),
    path("", include("apps.tickets.urls")),
    path("", include("apps.users.urls")),
    path("", include("apps.diagnostics.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.routing.urls")),
    path("", include("apps.technicians.urls")),
    path("", include("apps.schedules.urls")),
    path("", include("apps.assets.urls")),
    path("", include("apps.agents.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.logs.urls")),
    path("", include("apps.manuals.urls")),
    path("", include("apps.staffs.urls")),
    path("ai/", include("apps.ai.urls")),
]
