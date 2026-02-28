from rest_framework.routers import DefaultRouter
from .views import TechnicianProfileViewSet, technician_search
from django.urls import path, include

router = DefaultRouter()
router.register(r"technicians", TechnicianProfileViewSet)

urlpatterns = [
    path("technician/search/", technician_search),
    path('', include(router.urls)),
]
# urlpatterns = router.urls
