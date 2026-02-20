from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = (
        ("order_approved", "Order Approved"),
        ("order_rejected", "Order Rejected"),
        ("order_created", "Order Created"),
    )
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
