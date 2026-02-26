import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        OFFICE = "office", "Office Staff"
        TECHNICIAN = "technician", "Technician"
        CUSTOMER = "customer", "Customer"
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CUSTOMER)
    REQUIRED_FIELDS = ["email", "role"]

    class Meta:
        indexes = [models.Index(fields=["role"])]

    def __str__(self):
        return self.username

    # -------- Role Helpers --------
    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN

    @property
    def is_office(self):
        return self.role == self.Roles.OFFICE

    @property
    def is_technician(self):
        return self.role == self.Roles.TECHNICIAN
     
    @property
    def is_customer(self):
        return self.role == self.Roles.CUSTOMER



class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_image = models.ImageField(upload_to="profile_images/", null=True, blank=True)
    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        null=True,
        blank=True
    )
    preferences = models.JSONField(default=dict, blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True)
    street_address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def image_url(self):
        if self.profile_image:
            return self.profile_image.url
        return ""


class AdminUserProfile(models.Model):    
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="admin_profile")
    STATUS = {
        ('Available', "Available"),
        ('Busy', 'Busy'),
        ('Unavailable', 'Unavailable')
    }
    status = models.CharField(max_length=50, default="Available")
    class Meta:
        verbose_name = "Admin User Profile"
        verbose_name_plural = "Admin User Profiles"
    def __str__(self):
        return f"{self.profile.user.username} - {self.profile.user.role}"

class Station(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    region = models.ForeignKey("Region", on_delete=models.SET_NULL, null=True, blank=True, related_name="stations")
    street_address = models.CharField(max_length=255, blank=True)
    street_address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name