from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tickets.models import Ticket
from apps.agents.assignment_agent import AssignmentAgent


@receiver(post_save, sender=Ticket)
def auto_assign_technician_on_create(sender, instance: Ticket, created: bool, **kwargs):
    """
    Auto-assign a technician whenever a Ticket is saved without one
    (API, admin, or scripts), by running the AssignmentAgent so logs
    and technician status updates are handled in one place.
    """
    if instance.assigned_technician:
        return

    agent = AssignmentAgent()
    agent.assign(instance)

