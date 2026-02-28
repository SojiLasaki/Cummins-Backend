from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TechnicianProfile

@receiver(post_save, sender=TechnicianProfile)
def set_technician_role(sender, instance, created, **kwargs):
    if created:
        user = instance.profile.user
        user.role = 'technician'
        user.save()
