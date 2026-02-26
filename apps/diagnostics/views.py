from django.shortcuts import render
from .models import DiagnosticReport
from .serializers import DiagnosticReportSerializer
from rest_framework import viewsets, filters
# Create your views here.

class DiagnosticReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Diagnostic Reports.
    Supports:
    - Listing all diagnostic reports
    - Retrieving a single report
    - Creating, updating, deleting reports
    """
    queryset = DiagnosticReport.objects.all().select_related(
        'assigned_technician__user', 'customer__user', 'component'
    ).prefetch_related('parts')
    
    serializer_class = DiagnosticReportSerializer
    lookup_field = "id"

    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = [
        'title',
        'severity',
        'status',
        'specialization',
        'expertise_requirement',
        'assigned_technician__user__first_name',
        'assigned_technician__user__last_name',
        'ticket__ticket_id'
    ]
    ordering_fields = ['created_at', 'resolved_at', 'severity']
    ordering = ['-created_at']