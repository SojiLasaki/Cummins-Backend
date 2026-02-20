from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from .models import Order
from .serializers import OrderSerializer
from .permissions import CanApproveOrder


class OrderViewSet(viewsets.ModelViewSet):

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [CanApproveOrder]

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    def perform_update(self, serializer):
        order = self.get_object()
        new_status = self.request.data.get("status")
        user = self.request.user

        if new_status == "approved":
            if not (user.is_admin or user.is_office):
                raise PermissionDenied("Only admin or office staff can approve orders.")

            serializer.save(status="approved", approved_by=user)
        else:
            serializer.save()
