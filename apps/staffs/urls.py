from rest_framework.routers import DefaultRouter
from .views import StaffProfileViewSet

router = DefaultRouter()
router.register(r"staffs", StaffProfileViewSet)

urlpatterns = router.urls
