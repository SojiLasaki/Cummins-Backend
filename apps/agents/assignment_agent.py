from datetime import timedelta

from django.utils import timezone

from apps.agents.assignment_engine import assign_best_technician
from apps.logs.models import ActivityLog
from apps.schedules.models import Schedule, end_other_active_schedules_for_technician


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

        # Step 3: Create or update schedule for this ticket with estimated finish time
        self._ensure_schedule_for_assignment(ticket, technician)

        # Step 4: Update technician status
        technician.status = "busy"
        technician.save()

        # Step 5: Log success
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

    def _ensure_schedule_for_assignment(self, ticket, technician):
        """
        Ensure there is a schedule entry for this ticket/technician.
        Uses ticket.estimated_resolution_time_minutes if set, otherwise
        falls back to a severity-based default.
        """
        if not ticket.customer:
            return

        has_schedule = Schedule.objects.filter(ticket=ticket, technician=technician).exists()
        if has_schedule:
            return

        # One active schedule per technician: end any other active schedule for this technician
        end_other_active_schedules_for_technician(technician)

        # Determine duration in minutes
        if ticket.estimated_resolution_time_minutes:
            minutes = ticket.estimated_resolution_time_minutes
        else:
            # Simple defaults by severity: higher severity → more time
            severity_defaults = {
                1: 60,    # Low   → 1 hour
                2: 120,   # Medium→ 2 hours
                3: 180,   # High  → 3 hours
                4: 240,   # Severe→ 4 hours
            }
            minutes = severity_defaults.get(ticket.severity or 2, 120)

        duration = timedelta(minutes=minutes)
        scheduled_time = ticket.assigned_at or timezone.now()

        Schedule.objects.create(
            customer=ticket.customer,
            technician=technician,
            ticket=ticket,
            scheduled_time=scheduled_time,
            duration=duration,
            description=f"Auto-scheduled for ticket {ticket.ticket_id or ticket.id}",
        )