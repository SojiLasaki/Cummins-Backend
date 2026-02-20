from django.db import transaction
from django.db.models import F
from .models import Part


def deduct_inventory(part_id, quantity):
    with transaction.atomic():
        part = Part.objects.select_for_update().get(id=part_id)
        if part.quantity_available < quantity:
            raise ValueError("Not enough inventory available")
        part.quantity_available = F("quantity_available") - quantity
        part.save(update_fields=["quantity_available"])
        part.refresh_from_db()
        return part


def add_inventory(part_id, quantity):
    with transaction.atomic():
        part = Part.objects.select_for_update().get(id=part_id)
        part.quantity_available = F("quantity_available") + quantity
        part.save(update_fields=["quantity_available"])
        part.refresh_from_db()

        return part
