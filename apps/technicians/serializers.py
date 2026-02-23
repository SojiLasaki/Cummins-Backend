from rest_framework import serializers
from .models import TechnicianProfile
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

User = get_user_model()


class TechnicianProfileSerializer(serializers.ModelSerializer):
    # Read-only user fields
    username_display = serializers.CharField(source="user.username", read_only=True)
    email_display = serializers.EmailField(source="user.email", read_only=True)
    first_name_display = serializers.CharField(source="user.first_name", read_only=True)
    last_name_display = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    station_name = serializers.CharField(source="station.name", read_only=True)
    station_street_address = serializers.CharField(source="station.astreet_ddress", read_only=True)
    station_street_address_2 = serializers.CharField(source="station.street_address_2", read_only=True)
    station_city = serializers.CharField(source="station.city", read_only=True)
    station_state = serializers.CharField(source="station.state", read_only=True)
    station_postal_code = serializers.CharField(source="station.postal_code", read_only=True)
    station_country = serializers.CharField(source="station.country", read_only=True)
    # Write fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = TechnicianProfile
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
            "street_address_2",
            "city",
            "state",
            "postal_code",
            "country",
            "specialization",
            "expertise",
            'status',
            'station',
            'station_name',
            'station_street_address',
            'station_street_address_2',
            'station_city',
            'station_state',
            'station_postal_code',
            'station_country',
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
            role=User.Roles.TECHNICIAN,
        )

        # Create AdminUserProfile directly
        profile = TechnicianProfile.objects.create(
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
    