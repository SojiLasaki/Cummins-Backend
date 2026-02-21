from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomerProfile
from django.utils.crypto import get_random_string

User = get_user_model()

class CustomerProfileSerializer(serializers.ModelSerializer):
    # Read-only user fields
    username_display = serializers.CharField(source="user.username", read_only=True)
    email_display = serializers.EmailField(source="user.email", read_only=True)
    first_name_display = serializers.CharField(source="user.first_name", read_only=True)
    last_name_display = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)

    # Write fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = CustomerProfile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "username_display",
            "email_display",
            "first_name_display",
            "last_name_display",
            "role",
            "phone_number",
            "street_address",
            "city",
            "state",
            "postal_code",
            "country",
            "company_name",
            'notes'
        ]

    def create(self, validated_data):
        # Pop user fields
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        password = get_random_string(length=10)

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=User.Roles.ADMIN,
        )

        # Create AdminUserProfile directly
        profile = CustomerProfile.objects.create(
            user=user,
            **validated_data  # now only profile fields like notes, phone_number
        )

        return profile
    
    def update(self, instance, validated_data):
        user = instance.user

        # Update user fields if provided
        user.username = validated_data.pop("username", user.username)
        user.email = validated_data.pop("email", user.email)
        user.first_name = validated_data.pop("first_name", user.first_name)
        user.last_name = validated_data.pop("last_name", user.last_name)
        user.save()

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance
    