from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.inventory.models import Part
from apps.notifications.utils import send_notification
from apps.orders.models import Order

User = get_user_model()


@receiver(post_save, sender=Order)
def deduct_inventory_on_approval(sender, instance, created, **kwargs):
    # During fixture loading (`loaddata`), Django sends signals with `raw=True`.
    # We must not run side effects (inventory deduction / notifications) in that mode.
    if kwargs.get("raw"):
        return

    if instance.status == "approved" and not instance.inventory_deducted:
        with transaction.atomic():
            part = Part.objects.select_for_update().get(id=instance.part.id)
            if part.quantity_available < instance.quantity:
                raise ValueError("Not enough inventory available.")

            part.quantity_available -= instance.quantity
            part.save(update_fields=["quantity_available"])
            instance.inventory_deducted = True
            instance.save(update_fields=["inventory_deducted"])


@receiver(pre_save, sender=Order)
def _capture_old_order_state(sender, instance: Order, **kwargs):
    if kwargs.get("raw"):
        return
    if not instance.pk:
        instance._old_status = None
        return
    try:
        old = Order.objects.get(pk=instance.pk)
        instance._old_status = old.status
    except Order.DoesNotExist:
        instance._old_status = None


def _admin_and_office_users():
    try:
        roles = (User.Roles.ADMIN, User.Roles.OFFICE)
        return User.objects.filter(role__in=roles)
    except Exception:
        return User.objects.filter(role__in=("admin", "office"))


@receiver(post_save, sender=Order)
def order_status_change(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    old_status = getattr(instance, "_old_status", None)
    new_status = instance.status

    def payload():
        return {
            "order_id": instance.id,
            "ticket_id": str(instance.ticket_id) if instance.ticket_id else None,
            "status": new_status,
        }

    if created:
        if instance.requested_by:
            transaction.on_commit(
                lambda: send_notification(
                    instance.requested_by,
                    "Order Created",
                    f"Your order #{instance.id} has been created.",
                    "order_created",
                    data=payload(),
                )
            )
        for u in _admin_and_office_users():
            transaction.on_commit(
                lambda u=u: send_notification(
                    u,
                    "New Order Created",
                    f"Order #{instance.id} was created and may need review.",
                    "order_created",
                    data=payload(),
                )
            )
        return

    if old_status == new_status:
        return

    if new_status == "approved":
        if instance.requested_by:
            transaction.on_commit(
                lambda: send_notification(
                    instance.requested_by,
                    "Order Approved",
                    f"Your order #{instance.id} has been approved.",
                    "order_approved",
                    data=payload(),
                )
            )
        return

    if new_status == "rejected":
        if instance.requested_by:
            transaction.on_commit(
                lambda: send_notification(
                    instance.requested_by,
                    "Order Rejected",
                    f"Your order #{instance.id} has been rejected.",
                    "order_rejected",
                    data=payload(),
                )
            )
        return

    if new_status == "received":
        ticket = getattr(instance, "ticket", None)
        tech_user = None
        if ticket and getattr(ticket, "assigned_technician", None) and getattr(ticket.assigned_technician, "profile", None):
            tech_user = ticket.assigned_technician.profile.user
        if tech_user:
            transaction.on_commit(
                lambda: send_notification(
                    tech_user,
                    "Parts Ready for Pickup",
                    f"Parts for ticket {ticket.ticket_id or ticket.id} are marked as received.",
                    "parts_ready_for_pickup",
                    data={
                        **payload(),
                        "ticket_ticket_id": ticket.ticket_id,
                    },
                )
            )