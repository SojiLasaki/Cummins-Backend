from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Profile, AdminUserProfile, OfficeStaffProfile
from apps.customers.models import CustomerProfile

@receiver(post_save, sender=User)
def create_user_profiles(sender, instance, created, **kwargs):
    if created:
        # Always create base profile
        profile = Profile.objects.create(user=instance)

        if instance.role == User.Roles.ADMIN:
            AdminUserProfile.objects.create(profile=profile)

        elif instance.role == User.Roles.OFFICE:
            OfficeStaffProfile.objects.create(profile=profile)

        elif instance.role == User.Roles.CUSTOMER:
            CustomerProfile.objects.create(user=instance)


@receiver(post_save, sender=AdminUserProfile)
def update_user_from_profile(sender, instance, created, **kwargs):
    if created:
        return
    user = getattr(instance, "user", None) or (
        getattr(instance, "profile", None) and getattr(instance.profile, "user", None)
    )
    if user is None:
        return
    if hasattr(instance, "username"):
        user.username = instance.username
    if hasattr(instance, "email"):
        user.email = instance.email
    if hasattr(instance, "first_name"):
        user.first_name = instance.first_name
    if hasattr(instance, "last_name"):
        user.last_name = instance.last_name
    if hasattr(instance, "role"):
        user.role = instance.role
    user.save()



@receiver(post_save, sender=AdminUserProfile)
def set_admin_role(sender, instance, created, **kwargs):
    if created:
        user = instance.profile.user
        user.role = 'admin'
        user.save()


@receiver(post_save, sender=OfficeStaffProfile)
def set_office_staff_role(sender, instance, created, **kwargs):
    if created:
        user = instance.profile.user
        user.role = 'office_staff'
        user.save()