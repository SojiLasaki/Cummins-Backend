from rest_framework.routers import DefaultRouter
from .views import TechnicianViewSet

router = DefaultRouter()
router.register(r"technicians", TechnicianViewSet)

urlpatterns = router.urls
