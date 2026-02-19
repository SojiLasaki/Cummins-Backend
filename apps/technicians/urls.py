from rest_framework.routers import DefaultRouter
from .views import TechnicianProfileViewSet

router = DefaultRouter()
router.register(r"technicians", TechnicianProfileViewSet)

urlpatterns = router.urls
