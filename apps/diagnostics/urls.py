from rest_framework.routers import DefaultRouter
from .views import diagnosticViewSet

router = DefaultRouter()
router.register(r"diagnostics", DiagnosticViewSet)

urlpatterns = router.urls
