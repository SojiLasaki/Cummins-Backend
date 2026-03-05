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
        """List schedules for this ticket. GET /api/tickets/{id}/schedules/

        If no schedules exist yet but the ticket is already assigned,
        lazily create one using the same logic as the assignment agent
        so the frontend always sees at least one schedule for active tickets.
        """
        ticket = self.get_object()
        qs = Schedule.objects.filter(ticket=ticket).select_related(
            "customer",
            "customer__user",
            "technician",
            "technician__profile",
            "technician__profile__user",
            "ticket",
        )

        # Lazy backfill: if ticket is already assigned but has no schedule yet,
        # create one using the same helper the assignment agent uses.
        if not qs.exists() and ticket.assigned_technician and ticket.customer:
            from apps.agents.assignment_agent import AssignmentAgent

            agent = AssignmentAgent()
            agent._ensure_schedule_for_assignment(ticket, ticket.assigned_technician)
            qs = Schedule.objects.filter(ticket=ticket).select_related(
                "customer",
                "customer__user",
                "technician",
                "technician__profile",
                "technician__profile__user",
                "ticket",
            )

        schedules = qs.order_by("scheduled_time")
        serializer = ScheduleListSerializer(schedules, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        # Ticket post_save signal handles technician auto-assignment so it works
        # for API, admin, and any other creation paths consistently.
        serializer.save(created_at=timezone.now())