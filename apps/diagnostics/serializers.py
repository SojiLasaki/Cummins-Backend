from rest_framework import serializers
from .models import DiagnosticReport

class DiagnosticReportSerializer(serializers.ModelSerializer):
    # assigned_technician = serializers.CharField(source='technicians.user.first_name' 'technicians.user.last_name', read_only=True)
    assigned_technician = serializers.SerializerMethodField()
    def get_assigned_technician(self, obj):
        if not obj.assigned_technician:
            return None
        return f"{obj.assigned_technician.user.first_name} {obj.assigned_technician.user.last_name}"
    company_name = serializers.CharField(source='customer.company_name', read_only=True)
    customer_first_name = serializers.CharField(source='customer.user.first_name', read_only=True)
    customer_last_name = serializers.CharField(source='customer.user.last_name', read_only=True)
    customer_street_address = serializers.CharField(source='customer.street_address', read_only=True)
    customer_street_address_2 = serializers.CharField(source='customer.street_address_2', read_only=True)
    customer_city = serializers.CharField(source='customer.city', read_only=True)
    customer_state = serializers.CharField(source='customer.state', read_only=True)
    customer_country = serializers.CharField(source='customer.country', read_only=True)
    customer_postal_code = serializers.CharField(source='customer.postal_code', read_only=True)
    component_name = serializers.CharField(source='component.name', read_only=True)
    component_id = serializers.CharField(source='component.id', read_only=True)
    part_id = serializers.CharField(source='part.id', read_only=True)
    part_name = serializers.StringRelatedField(many=True, read_only=True)
    class Meta:
        model = DiagnosticReport
        fields = [
            "id",
            'assigned_technician',
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
            "part_id",
            "part_name",
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