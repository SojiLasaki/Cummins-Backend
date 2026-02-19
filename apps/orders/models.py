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
    ticket = models.ForeignKey("tickets.Ticket", on_delete=models.CASCADE, related_name="purchase_orders")
    part = models.ForeignKey(Part, on_delete=models.CASCADE)
    customer = models.ForeignKey("customers.CustomerProfile", verbose_name=("Customer"), on_delete=models.CASCADE)
    reason = models.TextField()
    quantity = models.IntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    requested_by_agent = models.BooleanField(default=False)
    approved_by = models.ForeignKey("users.User", verbose_name=("Approved By"), null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
