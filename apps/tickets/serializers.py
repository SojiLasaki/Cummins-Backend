from rest_framework import serializers
from .models import Ticket
from apps.diagnostics.serializers import DiagnosticReportSerializer
from apps.inventory.serializers import PartSerializer


class TicketSerializer(serializers.ModelSerializer):
    diagnostic_reports = DiagnosticReportSerializer(many=True, read_only=True)
    parts = PartSerializer(many=True, read_only=True)
    assigned_technician_profile_id = serializers.SerializerMethodField(read_only=True)
    assigned_technician_username = serializers.SerializerMethodField(read_only=True)
    assigned_technician_first_name = serializers.SerializerMethodField(read_only=True)
    assigned_technician_last_name = serializers.SerializerMethodField(read_only=True)
    assigned_technician_id = serializers.SerializerMethodField(read_only=True)

    # Customer display fields
    customer_first_name = serializers.CharField(
        source="customer.user.first_name", read_only=True
    )
    customer_last_name = serializers.CharField(
        source="customer.user.last_name", read_only=True
    )
    # customer_name = serializers.SerializerMethodField(read_only=True)
    customer_street_address = serializers.CharField(
        source="customer.street_address", read_only=True
    )
    customer_street_address_2 = serializers.CharField(
        source="customer.street_address_2", read_only=True
    )
    customer_city = serializers.CharField(
        source="customer.city", read_only=True
    )
    customer_state = serializers.CharField(
        source="customer.state", read_only=True
    )
    customer_postal_code = serializers.CharField(
        source="customer.postal_code", read_only=True
    )
    customer_country = serializers.CharField(
        source="customer.country", read_only=True
    )

    def get_assigned_technician_profile_id(self, obj):
        if obj.assigned_technician and getattr(obj.assigned_technician, "profile", None):
            return obj.assigned_technician.profile.id
        return None

    def get_assigned_technician_username(self, obj):
        if obj.assigned_technician and getattr(obj.assigned_technician, "profile", None):
            return obj.assigned_technician.profile.user.username
        return None

    def get_assigned_technician_first_name(self, obj):
        if obj.assigned_technician and getattr(obj.assigned_technician, "profile", None):
            return getattr(obj.assigned_technician.profile.user, "first_name", None) or ""
        return ""

    def get_assigned_technician_last_name(self, obj):
        if obj.assigned_technician and getattr(obj.assigned_technician, "profile", None):
            return getattr(obj.assigned_technician.profile.user, "last_name", None) or ""
        return ""

    def get_assigned_technician_id(self, obj):
        return obj.assigned_technician_id if obj.assigned_technician_id else None

    def get_customer_name(self, obj):
        if not getattr(obj, "customer", None):
            return ""
        u = getattr(obj.customer, "user", None)
        if not u:
            return ""
        full = f"{u.first_name or ''} {u.last_name or ''}".strip()
        return full or u.username

    class Meta:
        model = Ticket
        fields = [
            'id',
            "ticket_id",
            "assigned_technician_id",
            'assigned_technician_username',
            "assigned_technician_profile_id",
            "assigned_technician_first_name",
            "assigned_technician_last_name",
            "customer",
            "customer_first_name",
            "customer_last_name",
            # "customer_name",
            "customer_street_address",
            "customer_street_address_2",
            "customer_city",
            "customer_state",
            "customer_postal_code",
            "customer_country",
            "specialization",
            "title",
            "description",
            "issue_description",
            "severity",
            "status",
            "priority",
            "customer_satisfaction_rating",
            "estimated_resolution_time_minutes",
            "actual_resolution_time_minutes",
            "predicted_resolution_summary",
            "auto_assigned",
            "parts",
            "created_by",
            "created_at",
            "assigned_at",
            "resolved_at",
            "closed_at",
            "diagnostic_reports",
        ]
