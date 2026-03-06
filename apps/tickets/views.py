from django.db.models import Q
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .models import Ticket
from .serializers import TicketSerializer
from apps.agents.assignment_engine import assign_best_technician
from apps.schedules.models import Schedule
from apps.schedules.serializers import ScheduleListSerializer
from django.utils import timezone
from .checklists import ensure_ticket_checklist, regenerate_ticket_checklist
from .id_generation import generate_ticket_id
from .services.repair_time_and_cost import get_repair_time_stats


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
            "customer__user",
        ).prefetch_related("parts", "diagnostic_reports", "schedules")
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

    @action(detail=False, methods=["get"], url_path="repair-time-stats")
    def repair_time_stats(self, request):
        """
        GET /api/tickets/repair-time-stats/
        Returns average repair time (predicted and actual) and descriptions.
        Optional query params: status=... to filter tickets.
        """
        qs = self.get_queryset()
        stats = get_repair_time_stats(qs)
        return Response(stats)

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
        validated = getattr(serializer, "validated_data", {})
        save_kwargs = {"created_at": timezone.now()}
        if not str(validated.get("ticket_id") or "").strip():
            save_kwargs["ticket_id"] = generate_ticket_id()
        if not str(validated.get("created_by") or "").strip():
            username = str(getattr(self.request.user, "username", "") or "").strip()
            if username:
                save_kwargs["created_by"] = username
        ticket = serializer.save(**save_kwargs)
        ensure_ticket_checklist(ticket)

    @action(detail=True, methods=["post"], url_path="regenerate_checklist")
    def regenerate_checklist(self, request, pk=None):
        """Forcefully regenerate the checklist, replacing existing template."""
        ticket = self.get_object()
        regenerate_ticket_checklist(ticket)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="sync_checklist")
    def sync_checklist(self, request, pk=None):
        """Generate checklist only if the ticket doesn't already have one.

        Use this endpoint to manually trigger checklist generation for tickets
        that were created without a checklist (e.g., legacy tickets or those
        created through other channels). Unlike regenerate_checklist, this
        preserves any existing checklist.
        """
        ticket = self.get_object()
        ensure_ticket_checklist(ticket)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="checklist_progress")
    def checklist_progress(self, request, pk=None):
        ticket = self.get_object()
        payload = request.data if isinstance(request.data, dict) else {}
        incoming = payload.get("progress", payload)
        if not isinstance(incoming, list):
            return Response({"error": "progress must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        template = ticket.checklist_template if isinstance(ticket.checklist_template, list) else []
        valid_ids = {str(item.get("id") or "").strip() for item in template if isinstance(item, dict)}
        valid_ids.discard("")

        normalized = []
        for row in incoming:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("item_id") or "").strip()
            if not item_id or item_id not in valid_ids:
                return Response(
                    {"error": f"Invalid checklist item_id: {item_id or '<empty>'}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            normalized.append(
                {
                    "item_id": item_id,
                    "done": bool(row.get("done", False)),
                    "note": str(row.get("note") or ""),
                    "flagged": bool(row.get("flagged", False)),
                    "time_minutes": _safe_time_minutes(row.get("time_minutes")),
                    "photos": row.get("photos") if isinstance(row.get("photos"), list) else [],
                    "updated_by": getattr(request.user, "username", "unknown"),
                    "updated_at": timezone.now().isoformat(),
                }
            )

        ticket.checklist_progress = normalized
        ticket.save(update_fields=["checklist_progress"])
        return Response(TicketSerializer(ticket).data, status=status.HTTP_200_OK)


def _safe_time_minutes(value):
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(minutes, 0)
