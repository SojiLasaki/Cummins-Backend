from rest_framework.routers import DefaultRouter
from .views import AdminUserProfileViewSet, ProfileViewSet

router = DefaultRouter()
router.register(r"admin-users", AdminUserProfileViewSet, basename="admin-users")
router.register(r"all-users", ProfileViewSet, basename="all-users")

urlpatterns = router.urls
