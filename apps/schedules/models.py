from django.db import models
from django.utils import timezone
from apps.customers.models import CustomerProfile
from apps.technicians.models import TechnicianProfile
from apps.tickets.models import Ticket
import uuid
# Create your models here.


def end_other_active_schedules_for_technician(technician):
    """
    Set ended_at=now() on all schedules for this technician that are still active.
    Call before creating a new schedule so a technician only has one active schedule at a time.
    """
    Schedule.objects.filter(technician=technician, ended_at__isnull=True).update(ended_at=timezone.now())


class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='schedules')
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name='schedules')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='schedules', null=True, blank=True)
    scheduled_time = models.DateTimeField()
    duration = models.DurationField()
    description = models.TextField(blank=True)
    ended_at = models.DateTimeField(null=True, blank=True, help_text="When this schedule was stopped (technician moved to another ticket).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self):
        """True if the technician is still working on this schedule (not ended)."""
        return self.ended_at is None

    @property
    def estimated_end_time(self):
        """
        Convenience property: when this schedule is expected to finish.
        """
        if not self.scheduled_time or not self.duration:
            return None
        return self.scheduled_time + self.duration

    def __str__(self):
        return f"Schedule for {self.customer.user.username} with {self.technician.profile.user.username} at {self.scheduled_time}"