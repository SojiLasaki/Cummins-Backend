from django.contrib import admin
from .models import User, Profile, AdminUserProfile, Station

# Register your models here.

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(AdminUserProfile)
admin.site.register(Station)