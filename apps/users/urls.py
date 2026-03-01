from rest_framework.routers import DefaultRouter
from .views import AdminUserProfileViewSet, ProfileViewSet, StationViewSet, RegionViewSet
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from .serializers import LoginView

router = DefaultRouter()
router.register(r"admin-users", AdminUserProfileViewSet, basename="admin-users")
router.register(r"all-users", ProfileViewSet, basename="all-users")
router.register(r"stations", StationViewSet, basename="stations")
router.register(r"regions", RegionViewSet, basename="regions")

urlpatterns = [
    # Keep both variants so clients posting without trailing slash do not fail.
    path("auth/login", LoginView.as_view(), name="login_no_slash"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="token_refresh_no_slash"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path('', include(router.urls)),
]


# urlpatterns = router.urls
