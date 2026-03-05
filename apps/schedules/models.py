from django.db import models
from django.utils import timezone
from apps.customers.models import CustomerProfile
from apps.technicians.models import TechnicianProfile
from apps.tickets.models import Ticket
import uuid
from datetime import datetime, time, timedelta


# Core working-hours constraints
WORK_START_HOUR = 9   # 9 AM
WORK_END_HOUR = 17    # 5 PM
MAX_HOURS_PER_DAY = 8.0


def end_other_active_schedules_for_technician(technician):
    """
    Set ended_at=now() on all schedules for this technician that are still active.
    Call before creating a new schedule so a technician only has one active schedule at a time.
    """
    Schedule.objects.filter(technician=technician, ended_at__isnull=True).update(
        ended_at=timezone.now()
    )


def normalize_schedule_start(technician, scheduled_time, duration):
    """
    Adjust scheduled_time so:
    - Work happens only between 9 AM and 5 PM
    - Total scheduled hours for that technician on a given day do not exceed 8
    - If it would overflow the day or 8 hours, the schedule is pushed to the next day at 9 AM.
    """
    from django.db.models import Sum

    if not scheduled_time:
        scheduled_time = timezone.now()

    duration_hours = duration.total_seconds() / 3600.0
    tz = timezone.get_current_timezone()
    candidate = scheduled_time

    while True:
        local = candidate.astimezone(tz)
        day = local.date()

        day_start = timezone.make_aware(
            datetime.combine(day, time(WORK_START_HOUR, 0)), tz
        )
        day_end = timezone.make_aware(
            datetime.combine(day, time(WORK_END_HOUR, 0)), tz
        )

        # Clamp start into working window
        if candidate < day_start:
            candidate = day_start
            local = candidate.astimezone(tz)

        # If already past working hours, move to next day 9 AM
        if candidate >= day_end:
            next_day = day + timedelta(days=1)
            candidate = timezone.make_aware(
                datetime.combine(next_day, time(WORK_START_HOUR, 0)), tz
            )
            continue

        # Total hours already scheduled that day for this technician
        agg = (
            Schedule.objects.filter(
                technician=technician,
                scheduled_time__date=day,
            ).aggregate(total=Sum("duration"))
        )
        total_duration = agg.get("total") or timedelta(0)
        day_hours = total_duration.total_seconds() / 3600.0

        # If adding this schedule would exceed 8 hours, move to next day
        if day_hours + duration_hours > MAX_HOURS_PER_DAY:
            next_day = day + timedelta(days=1)
            candidate = timezone.make_aware(
                datetime.combine(next_day, time(WORK_START_HOUR, 0)), tz
            )
            continue

        # Ensure schedule fits within 9–5 window; otherwise push to next day
        end = candidate + duration
        if end > day_end:
            next_day = day + timedelta(days=1)
            candidate = timezone.make_aware(
                datetime.combine(next_day, time(WORK_START_HOUR, 0)), tz
            )
            continue

        return candidate


# Create your models here.


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