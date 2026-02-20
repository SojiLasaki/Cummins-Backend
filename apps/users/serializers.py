from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import AdminUserProfile, Profile

User = get_user_model()
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "street_address",
            "city",
            "state",
            "postal_code",
            "country",
        ]

class AdminUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = AdminUserProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "street_address",
            "city",
            "state",
            "postal_code",
            "country",
            "notes",
        ]

    def create(self, validated_data):
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=User.objects.make_random_password(),
            role=User.Roles.ADMIN  
        )

        # Create profile
        profile = AdminUserProfile.objects.create(
            user=user,
            **validated_data
        )

        return profile

    