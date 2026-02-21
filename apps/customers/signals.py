from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, CustomerProfile

@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    if created and instance.role == User.Roles.CUSTOMER:
        CustomerProfile.objects.create(
            user=instance,
            username=instance.username,
            email=instance.email,
            first_name=instance.first_name,
            last_name=instance.last_name,
            role=instance.role
        )