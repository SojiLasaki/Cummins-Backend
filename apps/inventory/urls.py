from rest_framework.routers import DefaultRouter
from .views import InventoryTransactionViewSet, ComponentViewSet, PartViewSet

router = DefaultRouter()
router.register(r"inventory", InventoryTransactionViewSet)
router.register(r"components", ComponentViewSet)
router.register(r"parts", PartViewSet)

urlpatterns = router.urls
