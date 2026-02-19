from django.db import models
from apps.tickets.models import Ticket
import uuid

class DiagnosticReport(models.Model):

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    ai_summary = models.TextField()
    probable_cause = models.TextField()
    recommended_actions = models.TextField()
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    def __str__(self):
        return f"Diagnostic Report for Ticket {self.ticket.id}"