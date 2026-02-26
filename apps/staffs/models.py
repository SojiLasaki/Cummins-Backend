from django.db import models
from apps.users.models import Profile
from apps.users.models import Station
# Create your models here.

class StaffProfile(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="staff_profile")
    STATUS = {
        ('Available', "Available"),
        ('Busy', 'Busy'),
        ('Unavailable', 'Unavailable')
    }
    station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, default="Available")
    class Meta:
        verbose_name = "Staff Profile"
        verbose_name_plural = "Staff Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.user.role}"