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
