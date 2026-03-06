from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DiagnosticReportViewSet, FailureDetectedView, StaffReportViewSet

router = DefaultRouter()
router.register(r"diagnostics", DiagnosticReportViewSet)
router.register(r'staffb-reports', StaffReportViewSet)  

urlpatterns = [
    path("workflow/failure-detected/", FailureDetectedView.as_view(), name="workflow-failure-detected"),
]
urlpatterns += router.urls
