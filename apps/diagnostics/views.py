from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import DiagnosticReport, TechnicianReport
from .serializers import TechnicianReportSerializer
from .serializers import DiagnosticReportSerializer
from apps.core.services.system_orchestrator import SystemOrchestrator


# ------------------------------
# 1️⃣ Read-Only Diagnostic Reports
# ------------------------------
class DiagnosticReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Diagnostic Reports.
    Only listing and retrieval allowed.
    Creation is handled by the orchestrator via ticket workflow.
    """
    queryset = DiagnosticReport.objects.all().select_related(
        'assigned_technician__profile__user', 'customer', 'component'
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
        'assigned_technician__profile__user__first_name',
        'assigned_technician__profile__user__last_name',
        'ticket__ticket_id'
    ]
    ordering_fields = ['created_at', 'resolved_at', 'severity']
    ordering = ['-created_at']


# ------------------------------
# 2️⃣ Ticket Creation API
# ------------------------------
class CreateTicketView(APIView):
    """
    Frontend creates a ticket.
    Orchestrator automatically:
    - Creates DiagnosticReport
    - Calculates severity
    - Assigns technician
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ticket_data = request.data

        orchestrator = SystemOrchestrator()
        try:
            report = orchestrator.run_full_diagnostic_pipeline(ticket_data)

            return Response({
                "report_id": report.id,
                "assigned_technician": report.assigned_technician.id if report.assigned_technician else None,
                "severity": report.severity,
                "status": report.status
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ------------------------------
# 3️⃣ Technician Report Submission
# ------------------------------
class TechnicianReportViewSet(viewsets.ModelViewSet):
    """
    Technicians submit reports for tickets assigned to them.
    Only the assigned technician can create a report.
    Ticket & DiagnosticReport status updated automatically.
    """
    queryset = TechnicianReport.objects.all()
    serializer_class = TechnicianReportSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        technician_profile = self.request.user.profile.technician_profile
        ticket = serializer.validated_data["ticket"]

        if ticket.assigned_technician != technician_profile:
            raise PermissionDenied("You are not assigned to this ticket.")

        # Save the technician report
        serializer.save(technician=technician_profile)

        # Update the diagnostic report / ticket status
        ticket.status = "resolved"
        ticket.resolved_at = timezone.now()
        ticket.save()