from django.db import models

# Create your models here.

class Ticket(models.Model):

    STATUS_CHOICES = (
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("awaiting_parts", "Awaiting Parts"),
        ("awaiting_approval", "Awaiting Approval"),
        ("completed", "Completed"),
    )
    customer = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="tickets")
    product_id = models.CharField(max_length=100)
    issue_description = models.TextField()
    assigned_to = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.id} - {self.product_id} - {self.status}"