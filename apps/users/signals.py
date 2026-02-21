# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from .models import User, AdminUserProfile

# @receiver(post_save, sender=User)
# def create_admin_profile(sender, instance, created, **kwargs):
#     if created:
#         user = instance
#         profile = AdminUserProfile.objects.create(
#             user=user,
#             username=user.username,
#             email=user.email,
#             first_name=user.first_name,
#             last_name=user.last_name,
#             role = user.role
#         )

# def updateUser(sender, instance, created, **kwargs):
#     profile = instance
#     user = profile.user

#     if created == False:
#         user.first_name = profile.first_name
#         user.last_name = profile.last_name
#         user.username = profile.username
#         user.email = profile.email
#         user.role = user.role
#         user.save()

# def deleteUser(sender, instance, **kwargs):
#     try:
#         user = instance.user
#         user.delete()
#     except:
#         pass


# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     instance.profile.save()


# post_save.connect(create_user_profile, sender=User)
# post_save.connect(updateUser, sender=Profile)
# post_delete.connect(deleteUser, sender=Profile)

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, AdminUserProfile

@receiver(post_save, sender=AdminUserProfile)
def update_user_from_profile(sender, instance, created, **kwargs):
    if not created:
        user = instance.user
        user.username = instance.username
        user.email = instance.email
        user.first_name = instance.first_name
        user.last_name = instance.last_name
        user.role = instance.role
        user.save()


@receiver(post_save, sender=AdminUserProfile)
def update_user_from_profile(sender, instance, created, **kwargs):
    if not created:
        user = instance.user
        user.username = instance.username
        user.email = instance.email
        user.first_name = instance.first_name
        user.last_name = instance.last_name
        user.role = instance.role
        user.save()