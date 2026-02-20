from rest_framework.routers import DefaultRouter
from .views import ManualViewSet, ComponentViewSet, TagViewSet, ImageViewSet

router = DefaultRouter()
router.register(r"manuals", ManualViewSet)
router.register(r"components", ComponentViewSet)
router.register(r"tags", TagViewSet)
router.register(r"images", ImageViewSet)

urlpatterns = router.urls
