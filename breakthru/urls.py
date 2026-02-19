"""
URL configuration for breakthru project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.tickets.urls")),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.diagnostics.urls")),
    path("api/", include("apps.orders.urls")),
    path("api/", include("apps.routing.urls")),
    path("api/", include("apps.technicians.urls")),
    path("api/", include("apps.assets.urls")),
    path("api/", include("apps.agents.urls")),
    path("api/", include("apps.customers.urls")),
    path("api/", include("apps.inventory.urls")),
    path("api/", include("apps.logs.urls")),
    path("api/", include("apps.manuals.urls")),
]
