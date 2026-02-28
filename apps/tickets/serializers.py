from rest_framework import serializers
from .models import Ticket
from apps.diagnostics.serializers import DiagnosticReportSerializer
from apps.inventory.serializers import PartSerializer

class TicketSerializer(serializers.ModelSerializer):
    diagnostic_reports = DiagnosticReportSerializer(many=True, read_only=True)
    parts = PartSerializer(many=True, read_only=True)
    assigned_technician_profile_id = serializers.UUIDField(
        source="assigned_technician.profile.id", read_only=True
    )
    assigned_technician_first_name = serializers.CharField(
        source="assigned_technician.profile.user.first_name", read_only=True
    )
    assigned_technician_last_name = serializers.CharField(
        source="assigned_technician.profile.user.last_name", read_only=True
    )

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_id',
            'assigned_technician_profile_id',
            'assigned_technician_first_name',
            'assigned_technician_last_name',
            'customer',
            'specialization',
            'title',
            'description',
            'severity',
            'status',
            'priority',
            'customer_satisfaction_rating',
            'estimated_resolution_time_minutes',
            'actual_resolution_time_minutes',
            'predicted_resolution_summary',
            'auto_assigned',
            'parts',
            'created_by',
            'created_at',
            'assigned_at',
            'resolved_at',
            'closed_at',
            'diagnostic_reports',
        ]
