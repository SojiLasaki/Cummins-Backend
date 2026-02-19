from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User
from django.conf import settings
import uuid
from django.core.validators import RegexValidator
# Create your models here. 
# class User(AbstractUser):

#     ROLE_CHOICES = (
#         ("admin", "Admin"),
#         ("office", "Office Staff"),
#         ("engine_tech", "Engine Technician"),
#         ("electrical_tech", "Electrical Technician"),
#         ('customer', 'Customer'),
#     )
#     LEVEL_CHOICES = (
#         ("junior", "Junior"),
#         ("mid", "Mid"),
#         ("senior", "Senior"),
#     )
#     role = models.CharField(max_length=30, choices=ROLE_CHOICES)
#     level = models.CharField(max_length=30, choices=LEVEL_CHOICES, null=True, blank=True)
#     phone_number = models.CharField(max_length=20, blank=True, null=True)

#     def __str__(self):
#         return self.username

# accounts/models.py
class User(AbstractUser):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("office", "Office Staff"),
        ("engine_tech", "Engine Technician"),
        ("electrical_tech", "Electrical Technician"),
        ('customer', 'Customer'),
    )
    email_address = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    # onboarding_complete = models.BooleanField(default=False)
    REQUIRED_FIELDS = ['email_address', 'role'] 

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return self.username
    



class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # username = models.CharField(max_length=150, null=True, blank=True, unique=True, validators=[RegexValidator(regex=r'^[\w.@+-]+$', message="Username may contain letters, digits and @/./+/-/_ characters.")])
    profile_image = models.ImageField(upload_to="profile_images/", null=True, blank=True)
    phone_number = models.CharField(max_length=20, validators=[
                                    RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
                                    ], null=True, blank=True
                                )
    preferences = models.JSONField(default=dict, blank=True)
    street_address = models.CharField(max_length=255, blank=True)
    street_address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def imageURL(self):
        try:
            url = self.profile_image.url
        except:
            url = ''
        return url    