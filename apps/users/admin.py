from django.contrib import admin
from .models import User, Profile, AdminUserProfile, Station, Region
from django.contrib.auth.admin import UserAdmin

# Register your models here.

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(AdminUserProfile)
admin.site.register(Station)
admin.site.register(Region)

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ("email", "username", "role", "is_staff")
    ordering = ("email",)

    fieldsets = UserAdmin.fieldsets + (
        ("Role Info", {"fields": ("role",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role Info", {"fields": ("role",)}),
    )