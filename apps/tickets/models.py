from django.db import models
from apps.customers.models import CustomerProfile
from django.conf import settings
from apps.technicians.models import TechnicianProfile
from apps.customers.models import CustomerProfile
import uuid


class Ticket(models.Model):
    SPECIALIZATION_CHOICES = (
        ("engine", "Engine Technician"),
        ("electrical", "Electrical Technician"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("awaiting_parts", "Awaiting Parts"),
        ("awaiting_approval", "Awaiting Approval"),
        ("completed", "Completed"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    )

    SEVERITY = (
        (1, "Low"),
        (2, "Medium"),
        (3, "High"),
        (4, "Severe"),
    )

    PRIORITY_LEVEL = (
        (1, "Low"),
        (2, "Medium"),
        (3, "High"),
        (4, "Urgent"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, unique=True, editable=False)
    ticket_id = models.CharField(max_length=190, unique=True, null=True, blank=True)
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True,
        blank=True,
    )
    assigned_technician = models.ForeignKey(
        "technicians.TechnicianProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets"
    )
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES, default="engine")
    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    severity = models.IntegerField(choices=SEVERITY, default=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")

    # Performance Tracking
    customer_satisfaction_rating = models.FloatField(null=True, blank=True)
    estimated_resolution_time_minutes = models.IntegerField(null=True, blank=True)
    actual_resolution_time_minutes = models.IntegerField(null=True, blank=True)

    # AI Insights
    predicted_resolution_summary = models.TextField(null=True, blank=True)
    auto_assigned = models.BooleanField(default=False)
    created_by = models.CharField(max_length=150, null=True, blank=True)
    # created_by = models.ForeignKey(
    #     'users.Profile',
    #     # settings.AUTH_USER_MODEL, 
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="tickets_created"
    # )
    priority = models.IntegerField(choices=PRIORITY_LEVEL, default=2)
    parts = models.ManyToManyField("inventory.Part", blank=True, related_name="tickets")
    issue_description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.ticket_id or self.id} - {self.status}"

    class Meta:
        ordering = ["-created_at"]