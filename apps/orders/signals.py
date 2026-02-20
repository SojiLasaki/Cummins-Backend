from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from apps.orders.models import Order
from apps.inventory.models import Part


@receiver(post_save, sender=Order)
def deduct_inventory_on_approval(sender, instance, created, **kwargs):
    if instance.status == "approved" and not instance.inventory_deducted:
        with transaction.atomic():
            part = Part.objects.select_for_update().get(id=instance.part.id)
            if part.quantity < instance.quantity:
                raise ValueError("Not enough inventory available.")

            part.quantity -= instance.quantity
            part.save()
            instance.inventory_deducted = True
            instance.save(update_fields=["inventory_deducted"])


@receiver(post_save, sender=Order)
def order_status_change(sender, instance, created, **kwargs):
    if created:
        # New order created
        send_order_notification(
            instance.requested_by,
            "Order Created",
            f"Your order #{instance.id} has been created.",
            "order_created"
        )
    elif instance.status == "approved":
        send_order_notification(
            instance.requested_by,
            "Order Approved",
            f"Your order #{instance.id} has been approved.",
            "order_approved"
        )
    elif instance.status == "rejected":
        send_order_notification(
            instance.requested_by,
            "Order Rejected",
            f"Your order #{instance.id} has been rejected.",
            "order_rejected"
        )