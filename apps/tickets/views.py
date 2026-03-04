from django.db.models import Q
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Ticket
from .serializers import TicketSerializer
from apps.agents.assignment_engine import assign_best_technician
from apps.schedules.models import Schedule
from apps.schedules.serializers import ScheduleListSerializer
from django.utils import timezone


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "ticket_id",
        "title",
        "description",
        "issue_description",
        "status",
    ]
    ordering_fields = [
        "created_at",
        "assigned_at",
        "resolved_at",
        "closed_at",
        "status",
        "priority",
        "severity",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Ticket.objects.select_related(
            "assigned_technician",
            "assigned_technician__profile",
            "assigned_technician__profile__user",
            "customer",
        ).prefetch_related("parts", "diagnostic_reports")
        # Filter by assigned technician: profile_id (UUID) or technician pk (int)
        assigned_technician = self.request.query_params.get("assigned_technician")
        if assigned_technician:
            qs = qs.filter(
                Q(assigned_technician__profile__id=assigned_technician)
                | Q(assigned_technician__pk=assigned_technician)
            )
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    @action(detail=True, methods=["get"], url_path="schedules")
    def schedules(self, request, pk=None):
        """List schedules for this ticket. GET /api/tickets/{id}/schedules/"""
        ticket = self.get_object()
        schedules = Schedule.objects.filter(ticket=ticket).select_related(
            "customer", "customer__user", "technician", "technician__profile", "technician__profile__user", "ticket"
        ).order_by("scheduled_time")
        serializer = ScheduleListSerializer(schedules, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        ticket = serializer.save(created_at=timezone.now())
        technician = assign_best_technician(ticket)
        if technician:
            ticket.assigned_technician = technician
            ticket.auto_assigned = True
            ticket.assigned_at = timezone.now()
            ticket.save()