from rest_framework.routers import DefaultRouter
from .views import ManualViewSet

router = DefaultRouter()
router.register(r"manuals", ManualViewSet)

urlpatterns = router.urls
