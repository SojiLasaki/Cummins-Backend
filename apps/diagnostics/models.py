from django.db import models
from apps.tickets.models import Ticket
import uuid

class DiagnosticReport(models.Model):
    LEVEL = (
        ('Junior', 'Junior'),
        ('Mid', 'Mid'),
        ('Senior', 'Senior'),
    )
    POSITION_CHOICES = (
        ("Engine", "Engine_Technician"),
        ("Electrical", "Electrical_Technician"),
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES, default="Engine")
    expertise_requirement = models.CharField(max_length=50, choices=LEVEL, default="Junior")
    ai_summary = models.TextField()
    probable_cause = models.TextField()
    recommended_actions = models.TextField()
    confidence_score = models.FloatField()
    identified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"Diagnostic Report for Ticket {self.ticket.id}"