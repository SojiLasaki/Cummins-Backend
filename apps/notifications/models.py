from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = (
        ("order_approved", "Order Approved"),
        ("order_rejected", "Order Rejected"),
        ("order_created", "Order Created"),
        ("ticket_created", "Ticket Created"),
        ("ticket_assigned", "Ticket Assigned"),
        ("ticket_status_changed", "Ticket Status Changed"),
        ("parts_ready_for_pickup", "Parts Ready For Pickup"),
        ("asset_updated", "Asset Updated"),
    )
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
