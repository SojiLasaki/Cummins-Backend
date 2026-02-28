from rest_framework.routers import DefaultRouter
from .views import DiagnosticReportViewSet, TechnicianReportViewSet

router = DefaultRouter()
router.register(r"diagnostics", DiagnosticReportViewSet)
router.register(r'technician-reports', TechnicianReportViewSet)  

urlpatterns = router.urls
