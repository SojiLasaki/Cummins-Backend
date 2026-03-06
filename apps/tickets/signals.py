from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.tickets.models import Ticket
from apps.agents.assignment_agent import AssignmentAgent
from apps.notifications.utils import send_notification
from apps.tickets.patterns import upsert_pattern_from_completed_ticket

User = get_user_model()


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


@receiver(pre_save, sender=Ticket)
def _capture_old_ticket_state(sender, instance: Ticket, **kwargs):
    if not instance.pk:
        instance._old_status = None
        instance._old_assigned_technician_id = None
        return
    try:
        old = Ticket.objects.get(pk=instance.pk)
        instance._old_status = old.status
        instance._old_assigned_technician_id = old.assigned_technician_id
    except Ticket.DoesNotExist:
        instance._old_status = None
        instance._old_assigned_technician_id = None


def _admin_users():
    try:
        return User.objects.filter(role=User.Roles.ADMIN)
    except Exception:
        return User.objects.filter(role="admin")


@receiver(post_save, sender=Ticket)
def notify_on_ticket_events(sender, instance: Ticket, created: bool, **kwargs):
    old_status = getattr(instance, "_old_status", None)
    old_tech_id = getattr(instance, "_old_assigned_technician_id", None)

    def payload():
        return {
            "ticket_id": str(instance.id),
            "ticket_ticket_id": instance.ticket_id,
            "status": instance.status,
            "severity": instance.severity,
            "priority": instance.priority,
        }

    # Ticket created -> admins + customer
    if created:
        for u in _admin_users():
            transaction.on_commit(
                lambda u=u: send_notification(
                    u,
                    "New Ticket Created",
                    f"Ticket {instance.ticket_id or instance.id} was created.",
                    "ticket_created",
                    data=payload(),
                )
            )
        if instance.customer and getattr(instance.customer, "user", None):
            transaction.on_commit(
                lambda: send_notification(
                    instance.customer.user,
                    "Ticket Created",
                    f"Your ticket {instance.ticket_id or instance.id} has been created.",
                    "ticket_created",
                    data=payload(),
                )
            )

    # Technician assigned (or changed) -> technician
    if instance.assigned_technician_id and instance.assigned_technician_id != old_tech_id:
        tech_user = None
        if getattr(instance.assigned_technician, "profile", None):
            tech_user = instance.assigned_technician.profile.user
        if tech_user:
            transaction.on_commit(
                lambda: send_notification(
                    tech_user,
                    "New Ticket Assigned",
                    f"You have been assigned ticket {instance.ticket_id or instance.id}.",
                    "ticket_assigned",
                    data=payload(),
                )
            )

    # Status changed -> customer + assigned technician
    if old_status is not None and instance.status != old_status:
        if instance.customer and getattr(instance.customer, "user", None):
            transaction.on_commit(
                lambda: send_notification(
                    instance.customer.user,
                    "Ticket Updated",
                    f"Ticket {instance.ticket_id or instance.id} status changed to '{instance.status}'.",
                    "ticket_status_changed",
                    data=payload(),
                )
            )

    if old_status != "completed" and instance.status == "completed":
        def _persist_pattern():
            try:
                upsert_pattern_from_completed_ticket(instance)
            except Exception:
                # Learning persistence should never block ticket lifecycle events.
                return

        transaction.on_commit(_persist_pattern)
        tech_user = None
        if instance.assigned_technician_id and getattr(instance.assigned_technician, "profile", None):
            tech_user = instance.assigned_technician.profile.user
        if tech_user:
            transaction.on_commit(
                lambda: send_notification(
                    tech_user,
                    "Ticket Status Updated",
                    f"Ticket {instance.ticket_id or instance.id} status changed to '{instance.status}'.",
                    "ticket_status_changed",
                    data=payload(),
                )
            )
