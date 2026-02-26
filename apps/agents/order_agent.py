# apps/orders/services/order_agent.py

from apps.inventory.models import Part
from apps.orders.models import Order


class OrderAgent:

    def handle_part_requirement(self, ticket, report):

        part_name = report.get("recommended_part")

        if not part_name:
            return

        try:
            part = Part.objects.get(name=part_name)
        except Part.DoesNotExist:
            return

        # If stock is low → place restock order
        if part.quantity_in_stock <= part.reorder_threshold:
            Order.objects.create(
                part=part,
                quantity=part.reorder_quantity,
                status="pending_admin_approval"
            )

        # Attach part to ticket if needed
        ticket.status = "awaiting_parts"
        ticket.save()