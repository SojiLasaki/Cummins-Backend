from django.db import models
from apps.users.models import Profile

# Create your models here.
class CustomerProfile(Profile):
    company_name = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"{self.username} - {self.company_name}"