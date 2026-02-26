from rest_framework import serializers
from .models import Ticket
from apps.diagnostics.serializers import DiagnosticReportSerializer

class TicketSerializer(serializers.ModelSerializer):
    diagnostic_reports = DiagnosticReportSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_id',
            'customer',
            'assigned_technician',
            'customer',
            'specialization',
            'title',
            'description',
            'severity',
            'status',
            'customer_satisfaction_rating',
            'estimated_resolution_time_minutes',
            'actual_resolution_time_minutes',
            'predicted_resolution_summary',
            'auto_assigned',
            'created_by',
            'created_at',
            'assigned_at',
            'resolved_at',
            'closed_at',
            'diagnostic_reports',
        ]