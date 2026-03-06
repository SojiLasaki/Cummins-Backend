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

    def get_queryset(self):
        base_qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        role = getattr(user, "role", None)
        customer_profile = getattr(user, "customer_profile", None) if user is not None else None
        customer_profile_id = getattr(customer_profile, "id", None) if customer_profile is not None else None

        qs = base_qs
        # Scope tickets based on role:
        # - Customers: only tickets for their CustomerProfile
        if role == "customer" and customer_profile_id is not None:
            qs = base_qs.filter(customer_id=customer_profile_id)

        return qs

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