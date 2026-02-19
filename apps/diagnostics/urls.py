from rest_framework.routers import DefaultRouter
from .views import DiagnosticReportViewSet

router = DefaultRouter()
router.register(r"diagnostics", DiagnosticReportViewSet)

urlpatterns = router.urls
