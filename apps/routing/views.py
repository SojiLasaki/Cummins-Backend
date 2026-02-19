from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.tickets.models import Ticket
from apps.technicians.models import TechnicianProfile
# Create your views here.


@api_view(["POST"])
def auto_assign(request, ticket_id):

    ticket = Ticket.objects.get(id=ticket_id)

    technician = TechnicianProfile.objects.filter(
        specialization="engine",
        is_available=True
    ).first()

    if technician:
        ticket.assigned_to = technician
        ticket.status = "assigned"
        ticket.save()

        return Response({"message": "Technician assigned"})
    
    return Response({"message": "No technician available"})
