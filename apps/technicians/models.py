from django.db import models
from apps.users.models import Profile
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
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    specialization = models.CharField(max_length=50, choices=POSITION_CHOICES)
    expertise = models.CharField(max_length=10, blank=True, choices=LEVEL)
    is_available = models.BooleanField(default=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.specialization}"