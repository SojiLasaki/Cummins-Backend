from django.shortcuts import render
from .models import DiagnosticReport
from .serializers import DiagnosticReportSerializer
from rest_framework import viewsets
# Create your views here.

class DiagnosticReportViewSet(viewsets.ModelViewSet):
    queryset = DiagnosticReport.objects.all()
    serializer_class = DiagnosticReportSerializer
    lookup_field = "id"