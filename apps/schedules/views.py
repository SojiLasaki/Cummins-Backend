from datetime import datetime
from django.utils import timezone
from rest_framework import viewsets, filters
from .models import Schedule
from .serializers import ScheduleSerializer, ScheduleListSerializer


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    Schedules workflow API.
    List: GET /api/schedules/
    Create: POST /api/schedules/
    Detail: GET /api/schedules/{id}/
    Update: PUT/PATCH /api/schedules/{id}/
    Delete: DELETE /api/schedules/{id}/

    Query params for list:
    - technician: technician profile id (UUID) or technician pk (int)
    - customer: customer id (UUID)
    - ticket: ticket id (UUID)
    - from_date: ISO datetime (inclusive)
    - to_date: ISO datetime (inclusive)
    - ordering: scheduled_time (default), -scheduled_time
    """
    queryset = Schedule.objects.all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["scheduled_time", "created_at"]
    ordering = ["scheduled_time"]

    def get_serializer_class(self):
        if self.action == "list":
            return ScheduleListSerializer
        return ScheduleSerializer

    def get_queryset(self):
        qs = Schedule.objects.select_related(
            "customer",
            "customer__user",
            "technician",
            "technician__profile",
            "technician__profile__user",
            "ticket",
        )
        # Filter by technician (pk or profile_id from query)
        technician = self.request.query_params.get("technician")
        if technician:
            from django.db.models import Q
            # Support both technician pk (int) and profile_id (UUID)
            qs = qs.filter(
                Q(technician__profile__id=technician) | Q(technician__pk=technician)
            )
        customer = self.request.query_params.get("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        from_date = self.request.query_params.get("from_date")
        if from_date:
            try:
                dt = timezone.make_aware(datetime.fromisoformat(from_date.replace("Z", "+00:00")))
                qs = qs.filter(scheduled_time__gte=dt)
            except (ValueError, TypeError):
                pass
        to_date = self.request.query_params.get("to_date")
        if to_date:
            try:
                dt = timezone.make_aware(datetime.fromisoformat(to_date.replace("Z", "+00:00")))
                qs = qs.filter(scheduled_time__lte=dt)
            except (ValueError, TypeError):
                pass
        return qs
