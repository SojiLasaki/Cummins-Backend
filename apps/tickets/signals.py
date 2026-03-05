from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tickets.models import Ticket
from apps.agents.assignment_agent import AssignmentAgent


@receiver(post_save, sender=Ticket)
def auto_assign_technician_on_save(sender, instance: Ticket, created: bool, **kwargs):
    """
    Auto-assign a technician whenever a Ticket is saved without one
    (API, Django admin, or scripts). Runs synchronously so it works reliably
    from the admin save.
    """
    if instance.assigned_technician_id:
        return

    agent = AssignmentAgent()
    agent.assign(instance)

