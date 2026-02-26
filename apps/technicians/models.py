from django.db import models
import uuid
from apps.users.models import Profile, Station
# from apps.tickets.models import Ticket
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
    skill_score = models.IntegerField(default=1)  # 1-10 scale
    
    def __str__(self):
        return f"{self.user.username} - {self.specialization}"
    

class Certification(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    technician = models.ForeignKey(TechnicianProfile, on_delete=models.CASCADE, related_name='certifications')
    certification_id = models.CharField(max_length=50, unique=True)
    institution = models.CharField(max_length=100)
    date_obtained = models.DateField()
    expiration_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.certification_id}"
