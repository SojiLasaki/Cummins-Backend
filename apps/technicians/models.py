from django.db import models
from apps.users.models import Profile, Station
# Create your models here.

class TechnicianProfile(Profile):
    LEVEL = (
        ('junior', 'Junior'),
        ('mid', 'Mid'),
        ('senior', 'Senior'),
    )
    POSITION_CHOICES = (
        ("engine", "Engine Technician"),
        ("electrical", "Electrical Technician"),
    )
    STATUS = {
        ('available', "Available"),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable')
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
    