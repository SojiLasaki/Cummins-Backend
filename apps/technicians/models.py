from django.db import models
import uuid
from apps.users.models import Profile, Station
# Create your models here.

class TechnicianProfile(Profile):
    LEVEL = (
        ('Junior', 'Junior'),
        ('Mid', 'Mid'),
        ('Senior', 'Senior'),
    )
    POSITION_CHOICES = (
        ("Engine", "Engine_Technician"),
        ("Electrical", "Electrical_Technician"),
    )
    STATUS = {
        ('Available', "Available"),
        ('Busy', 'Busy'),
        ('Unavailable', 'Unavailable')
    }
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES)
    expertise = models.CharField(max_length=10, blank=True, choices=LEVEL)
    status = models.CharField(max_length=27, choices=STATUS, default="Avaiable")
    station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True)
    # location = models.CharField(max_length=240, null=True, blank=True)
    # latitude = models.FloatField(null=True, blank=True)
    # longitude = models.FloatField(null=True, blank=True)

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