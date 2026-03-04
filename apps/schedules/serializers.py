from rest_framework import serializers
from .models import Schedule


class ScheduleListSerializer(serializers.ModelSerializer):
    """Minimal schedule for list: ids and times."""

    technician_id = serializers.PrimaryKeyRelatedField(
        source="technician", read_only=True
    )
    technician_profile_id = serializers.UUIDField(
        source="technician.profile.id", read_only=True
    )
    technician_display_name = serializers.SerializerMethodField()
    customer_id = serializers.UUIDField(source="customer.id", read_only=True)
    customer_display_name = serializers.SerializerMethodField()
    ticket_id = serializers.UUIDField(source="ticket.id", read_only=True, allow_null=True)
    ticket_ticket_id = serializers.CharField(
        source="ticket.ticket_id", read_only=True, allow_null=True
    )

    class Meta:
        model = Schedule
        fields = [
            "id",
            "scheduled_time",
            "duration",
            "description",
            "technician_id",
            "technician_profile_id",
            "technician_display_name",
            "customer_id",
            "customer_display_name",
            "ticket_id",
            "ticket_ticket_id",
            "created_at",
            "updated_at",
        ]

    def get_technician_display_name(self, obj):
        if not obj.technician or not obj.technician.profile:
            return ""
        u = obj.technician.profile.user
        return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username

    def get_customer_display_name(self, obj):
        if not obj.customer or not obj.customer.user:
            return ""
        return getattr(obj.customer.user, "username", "") or getattr(
            obj.customer, "company_name", ""
        )


class ScheduleSerializer(serializers.ModelSerializer):
    """Full schedule for create/update/retrieve; nested read-only summaries."""

    technician_id = serializers.PrimaryKeyRelatedField(
        source="technician", read_only=True
    )
    technician_profile_id = serializers.UUIDField(
        source="technician.profile.id", read_only=True, allow_null=True
    )
    technician_display_name = serializers.SerializerMethodField()
    customer_id = serializers.UUIDField(source="customer.id", read_only=True)
    customer_display_name = serializers.SerializerMethodField()
    ticket_id = serializers.UUIDField(source="ticket.id", read_only=True, allow_null=True)
    ticket_ticket_id = serializers.CharField(
        source="ticket.ticket_id", read_only=True, allow_null=True
    )
    ticket_title = serializers.CharField(
        source="ticket.title", read_only=True, allow_null=True
    )

    class Meta:
        model = Schedule
        fields = [
            "id",
            "customer",
            "technician",
            "ticket",
            "scheduled_time",
            "duration",
            "description",
            "technician_id",
            "technician_profile_id",
            "technician_display_name",
            "customer_id",
            "customer_display_name",
            "ticket_id",
            "ticket_ticket_id",
            "ticket_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_technician_display_name(self, obj):
        if not obj.technician or not getattr(obj.technician, "profile", None):
            return ""
        u = obj.technician.profile.user
        return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username

    def get_customer_display_name(self, obj):
        if not obj.customer or not getattr(obj.customer, "user", None):
            return ""
        return getattr(obj.customer.user, "username", "") or getattr(
            obj.customer, "company_name", ""
        )
