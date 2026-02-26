from django.utils import timezone
from apps.technicians.services.assignment_engine import assign_best_technician
from apps.logs.models import ActivityLog


class AssignmentAgent:

    def assign(self, ticket):
        """
        Assign the best available technician to a ticket.
        """

        # Step 1: Call scoring engine
        technician = assign_best_technician(ticket)

        if not technician:
            # Log failure
            ActivityLog.objects.create(
                event_type="agent_action",
                agent_name="AssignmentAgent",
                action="Technician Assignment",
                description="No eligible technician found",
                object_type="Ticket",
                object_id=ticket.id,
                status="failed",
                severity="warning",
            )
            return None

        # Step 2: Assign technician
        ticket.assigned_technician = technician
        ticket.status = "assigned"
        ticket.auto_assigned = True
        ticket.assigned_at = timezone.now()
        ticket.save()

        # Step 3: Update technician status
        technician.status = "Busy"
        technician.save()

        # Step 4: Log success
        ActivityLog.objects.create(
            event_type="agent_action",
            agent_name="AssignmentAgent",
            action="Technician Assigned",
            description=f"Ticket assigned to {technician}",
            object_type="Ticket",
            object_id=ticket.id,
            status="success",
            severity="info",
        )

        return technician