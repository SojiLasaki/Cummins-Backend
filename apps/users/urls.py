from rest_framework.routers import DefaultRouter
from .views import AdminUserProfileViewSet, ProfileViewSet, StationViewSet, RegionViewSet

router = DefaultRouter()
router.register(r"admin-users", AdminUserProfileViewSet, basename="admin-users")
router.register(r"all-users", ProfileViewSet, basename="all-users")
router.register(r"stations", StationViewSet, basename="stations")
router.register(r"regions", RegionViewSet, basename="regions")

urlpatterns = router.urls
