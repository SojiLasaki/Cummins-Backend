from django.shortcuts import render
from rest_framework import viewsets
from .models import Ticket
from .serializers import TicketSerializer
from apps.agents.assignment_engine import assign_best_technician
from django.utils import timezone
# Create your views here.


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

    def perform_create(self, serializer):
        # Save the ticket without created_by for now
        ticket = serializer.save(created_at=timezone.now())

        # Auto-assign technician
        technician = assign_best_technician(ticket)
        if technician:
            ticket.assigned_technician = technician
            ticket.auto_assigned = True
            ticket.assigned_at = timezone.now()
            ticket.save()