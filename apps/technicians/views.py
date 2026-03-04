from django.shortcuts import render
from django.db.models import Count
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TechnicianProfile
from .serializers import TechnicianProfileSerializer
from rest_framework.decorators import api_view
from apps.manuals.models import Manual
from apps.manuals.serializers import ManualSerializer
from apps.inventory.models import Part
from apps.inventory.serializers import PartSerializer
from apps.inventory.models import Component
from apps.inventory.serializers import ComponentSerializer
from apps.diagnostics.models import DiagnosticReport
from apps.diagnostics.serializers import DiagnosticReportSerializer
from apps.tickets.models import Ticket
from apps.tickets.serializers import TicketSerializer
from apps.schedules.models import Schedule
from apps.schedules.serializers import ScheduleListSerializer


class TechnicianProfileViewSet(viewsets.ModelViewSet):
    queryset = TechnicianProfile.objects.all()
    serializer_class = TechnicianProfileSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "profile__user__username",
        "profile__user__first_name",
        "profile__user__last_name",
        "profile__user__email",
    ]
    ordering_fields = ["profile__user__first_name", "total_jobs_completed", "date_joined", "skill_score"]
    ordering = ["profile__user__last_name", "profile__user__first_name"]

    def get_queryset(self):
        qs = (
            TechnicianProfile.objects.select_related("profile", "profile__user", "station")
            .prefetch_related("assigned_tickets")
            .annotate(_assigned_tickets_count=Count("assigned_tickets"))
        )
        # Optional query filters (no django-filter required)
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        specialization = self.request.query_params.get("specialization")
        if specialization:
            qs = qs.filter(specialization=specialization)
        station = self.request.query_params.get("station")
        if station:
            qs = qs.filter(station_id=station)
        return qs

    @action(detail=True, methods=["get"], url_path="tickets")
    def tickets(self, request, pk=None):
        """List tickets assigned to this technician. GET /api/technicians/{id}/tickets/"""
        technician = self.get_object()
        tickets = Ticket.objects.filter(assigned_technician=technician).order_by("-created_at")
        serializer = TicketSerializer(tickets, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="schedules")
    def schedules(self, request, pk=None):
        """List schedules for this technician. GET /api/technicians/{id}/schedules/"""
        technician = self.get_object()
        schedules = (
            Schedule.objects.filter(technician=technician)
            .select_related("customer", "customer__user", "technician", "technician__profile", "technician__profile__user", "ticket")
            .order_by("scheduled_time")
        )
        serializer = ScheduleListSerializer(schedules, many=True)
        return Response(serializer.data)


@api_view(["GET"])
def technician_search(request):
    query = request.GET.get("q", "")

    manuals = Manual.objects.filter(title__icontains=query)
    parts = Part.objects.filter(name__icontains=query)
    components = Component.objects.filter(name__icontains=query)
    diagnostics = DiagnosticReport.objects.filter(title__icontains=query)

    return Response({
        "manuals": ManualSerializer(manuals, many=True).data,
        "parts": PartSerializer(parts, many=True).data,
        "components": ComponentSerializer(components, many=True).data,
        "diagnostics": DiagnosticReportSerializer(diagnostics, many=True).data,
    })