# apps/tickets/services/ticketing_agent.py

from apps.tickets.models import Ticket
from apps.agents.assignment_engine import assign_best_technician
from django.utils import timezone


class TicketingAgent:

    def create_ticket_from_report(self, report):

        ticket = Ticket.objects.create(
            title=report["title"],
            description=report["description"],
            specialization=report["specialization"],
            severity=report["severity"],
            status="pending"
        )

        # Run technician assignment
        technician = assign_best_technician(ticket)

        if technician:
            ticket.assigned_technician = technician
            ticket.status = "assigned"
            ticket.auto_assigned = True
            ticket.assigned_at = timezone.now()
            ticket.save()

        # Trigger order agent
        from apps.agents.order_agent import OrderAgent
        OrderAgent().handle_part_requirement(ticket, report)

        return ticket