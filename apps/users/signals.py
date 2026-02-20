from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import User, Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        user = instance
        profile = Profile.objects.create(
            user=user,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name
        )

def updateUser(sender, instance, created, **kwargs):
    profile = instance
    user = profile.user

    if created == False:
        user.first_name = profile.first_name
        user.last_name = profile.last_name
        user.username = profile.username
        user.email = profile.email
        user.save()

def deleteUser(sender, instance, **kwargs):
    try:
        user = instance.user
        user.delete()
    except:
        pass


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


post_save.connect(create_user_profile, sender=User)
post_save.connect(updateUser, sender=Profile)
post_delete.connect(deleteUser, sender=Profile)