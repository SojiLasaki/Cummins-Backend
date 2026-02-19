from django.db import models
from apps.inventory.models import Part


class PurchaseOrder(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("ordered", "Ordered"),
        ("received", "Received"),
        ("rejected", "Rejected"),
    )

    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    requested_by_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
