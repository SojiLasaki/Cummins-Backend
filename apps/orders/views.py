from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from .models import Order
from .serializers import OrderSerializer
from .permissions import CanApproveOrder
from apps.inventory.models import Part
from apps.core.utils import is_connected


class OrderViewSet(viewsets.ModelViewSet):

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [CanApproveOrder]

    def perform_create(self, serializer):
        order = serializer.save(requested_by=self.request.user)

        if is_connected():
            # push immediately to Supabase
            from apps.sync.services.sync_service import sync_orders
            sync_orders()
        else:
            # set to sync later
            order.synced = False
            order.save()
            
        # Notifications are handled centrally in apps.orders.signals

    def perform_update(self, serializer):

        order = self.get_object()
        user = self.request.user
        new_status = self.request.data.get("status")

        with transaction.atomic():

            # APPROVAL LOGIC
            if new_status == "approved":
                if not (user.is_admin or user.is_office):
                    raise PermissionDenied("Only admin or office staff can approve orders.")

                if order.status == "approved":
                    raise PermissionDenied("Order already approved.")

                part = Part.objects.select_for_update().get(id=order.part.id)

                if part.quantity < order.quantity:
                    raise PermissionDenied("Not enough inventory available.")

                # Deduct inventory
                part.quantity -= order.quantity
                part.save()

                updated_order = serializer.save(
                    status="approved",
                    approved_by=user,
                    inventory_deducted=True
                )

                return

            # REJECTION LOGIC
            if new_status == "rejected":
                if not (user.is_admin or user.is_office):
                    raise PermissionDenied("Only admin or office staff can reject orders.")
                updated_order = serializer.save(
                    status="rejected",
                    approved_by=user
                )

                return

            # Normal update
            serializer.save()
