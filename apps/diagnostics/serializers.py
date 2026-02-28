from rest_framework import serializers
from .models import DiagnosticReport, TechnicianReport
from rest_framework import serializers
from .models import DiagnosticReport

class DiagnosticReportSerializer(serializers.ModelSerializer):
    assigned_technician = serializers.SerializerMethodField(read_only=True)
    
    def get_assigned_technician(self, obj):
        if not obj.assigned_technician:
            return None
        return f"{obj.assigned_technician.profile.user.first_name} {obj.assigned_technician.profile.user.last_name}"

    # Customer fields
    company_name = serializers.CharField(source='customer.company_name', read_only=True)
    customer_first_name = serializers.CharField(source='customer.user.first_name', read_only=True)
    customer_last_name = serializers.CharField(source='customer.user.last_name', read_only=True)
    customer_street_address = serializers.CharField(source='customer.street_address', read_only=True)
    customer_street_address_2 = serializers.CharField(source='customer.street_address_2', read_only=True)
    customer_city = serializers.CharField(source='customer.city', read_only=True)
    customer_state = serializers.CharField(source='customer.state', read_only=True)
    customer_country = serializers.CharField(source='customer.country', read_only=True)
    customer_postal_code = serializers.CharField(source='customer.postal_code', read_only=True)

    # Component fields
    component_id = serializers.CharField(source='component.id', read_only=True)
    component_name = serializers.CharField(source='component.name', read_only=True)

    # Part fields
    part_ids = serializers.PrimaryKeyRelatedField(source='parts', many=True, read_only=True)
    part_names = serializers.StringRelatedField(source='parts', many=True, read_only=True)

    class Meta:
        model = DiagnosticReport
        fields = [
            "id",
            'assigned_technician',
            'ticket_id',
            "diagnostics_id",
            "title",
            "severity",
            "status",
            "specialization",
            "expertise_requirement",
            'fault_code',
            'company_name',
            "customer",
            "customer_first_name",
            "customer_last_name",
            "customer_street_address",
            "customer_street_address_2",
            "customer_city",
            "customer_state",
            "customer_country",
            "customer_postal_code",
            "component_id",
            "component_name",
            "part_ids",
            "part_names",
            "ai_summary",
            "probable_cause",
            'description',
            "recommended_actions",
            "confidence_score",
            "identified_at",
            "resolved_at",
            "created_at",
            'performed_by',
        ]

    
class TechnicianReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianReport
        fields = ['id', 'ticket', 'technician', 'findings', 'actions_taken', 'parts_used', 'report_id', 'created_at']