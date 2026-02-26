from django.db import models
from apps.users.models import Profile

# Create your models here.
class CustomerProfile(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="customer_profile")
    company_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.profile.user.username} - {self.company_name}"