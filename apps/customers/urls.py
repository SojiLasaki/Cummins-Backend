from rest_framework.routers import DefaultRouter
from .views import CustomerProfileViewSet

router = DefaultRouter()
router.register(r"customers", CustomerProfileViewSet)

urlpatterns = router.urls
