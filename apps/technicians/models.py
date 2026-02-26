from django.db import models
from apps.users.models import Profile, Station
from apps.tickets.models import Ticket
# Create your models here.

class TechnicianProfile(models.Model):

    LEVEL = (
        ('junior', 'Junior'),
        ('mid', 'Mid'),
        ('senior', 'Senior'),
    )

    POSITION_CHOICES = (
        ('engine', 'Engine Technician'),
        ('electrical', 'Electrical Technician'),
    )

    STATUS = (
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    )
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="technician_profile")
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES)
    expertise = models.CharField(max_length=10, choices=LEVEL)
    status = models.CharField(max_length=20, choices=STATUS, default='available')
    station = models.ForeignKey(
        Station,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technicians"
    )
    total_years_experience = models.FloatField(default=0.0)
    date_joined = models.DateField(null=True, blank=True)
    performance_rating = models.FloatField(default=0.0)
    total_jobs_completed = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.profile.user.username} - {self.specialization}"
    

class TechnicianJob(models.Model):
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name='jobs')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='technician_jobs')
    severity = models.CharField(max_length=20, default='Medium')
    specialization = models.CharField(max_length=50, default='General')
    expertise = models.CharField(max_length=10, default='Mid')
    date_assigned = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job for {self.technician.user.username} - {self.severity} - {self.ticket.title}"