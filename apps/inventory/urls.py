from rest_framework.routers import DefaultRouter
from .views import InventoryViewSet

router = DefaultRouter()
router.register(r"inventory", InventoryViewSet)

urlpatterns = router.urls
