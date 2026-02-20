from django.db import models
import uuid
from apps.inventory.models import Component
# Create your models here.
# class Component(models.Model):
#     name = models.CharField(max_length=255, unique=True)
#     description = models.TextField(blank=True)
#     parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subcomponents")
#     id = models.AutoField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.name
    

class Manual(models.Model):
    title = models.CharField(max_length=255)
    component = models.ManyToManyField(Component, related_name="manuals", blank=True)
    parts_needed = models.ManyToManyField("inventory.Part", blank=True, related_name="manuals")
    version = models.CharField(max_length=50, blank=True, null=True)
    tags = models.ManyToManyField("Tag", blank=True, related_name="manuals")
    file = models.FileField(upload_to="manuals/", blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="manuals_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)

    def __str__(self):
        return f"{self.title} ({self.component})"
    

class Image(models.Model):
    manual = models.ForeignKey(Manual, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="manual_images/")
    caption = models.CharField(max_length=255, blank=True)
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.manual.title} - {self.caption}"
    

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    id = models.UUIDField(primary_key=True, editable=False, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
