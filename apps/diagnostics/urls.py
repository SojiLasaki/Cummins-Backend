from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DiagnosticReportViewSet, FailureDetectedView, TechnicianReportViewSet

router = DefaultRouter()
router.register(r"diagnostics", DiagnosticReportViewSet)
router.register(r'technician-reports', TechnicianReportViewSet)  

urlpatterns = [
    path("workflow/failure-detected/", FailureDetectedView.as_view(), name="workflow-failure-detected"),
]
urlpatterns += router.urls
