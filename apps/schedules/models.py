from django.db import models
from apps.customers.models import CustomerProfile
from apps.technicians.models import TechnicianProfile
from apps.tickets.models import Ticket
import uuid
# Create your models here.

class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='schedules')
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name='schedules')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='schedules', null=True, blank=True)
    scheduled_time = models.DateTimeField()
    duration = models.DurationField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Schedule for {self.customer.user.username} with {self.technician.user.username} at {self.scheduled_time}"