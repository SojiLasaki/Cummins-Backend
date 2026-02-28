from rest_framework import serializers
from .models import TechnicianProfile, Certification
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

User = get_user_model()

class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = ['id', 'name', 'certification_id', 'institution', 'date_obtained', 'expiration_date', 'technician']

class TechnicianProfileSerializer(serializers.ModelSerializer):
    # Read-only user fields
    id = serializers.CharField(source="profile.id", read_only=True)
    username_display = serializers.CharField(source="profile.user.username", read_only=True)
    phone_number = serializers.CharField(source="profile.user.phone_number", read_only=True)
    email_display = serializers.EmailField(source="profile.user.email", read_only=True)
    first_name_display = serializers.CharField(source="profile.user.first_name", read_only=True)
    last_name_display = serializers.CharField(source="profile.user.last_name", read_only=True)
    role = serializers.CharField(source="profile.user.role", read_only=True)
    street_address = serializers.CharField(source="profile.street_address", read_only=True)
    street_address_2 = serializers.CharField(source="profile.street_address_2", read_only=True)
    city = serializers.CharField(source="profile.city", read_only=True)
    state = serializers.CharField(source="profile.state", read_only=True)
    postal_code = serializers.CharField(source="profile.postal_code", read_only=True)
    country = serializers.CharField(source="profile.country", read_only=True)
    station_name = serializers.CharField(source="station.name", read_only=True)
    station_street_address = serializers.CharField(source="station.street_address", read_only=True)
    station_street_address_2 = serializers.CharField(source="station.street_address_2", read_only=True)
    station_city = serializers.CharField(source="station.city", read_only=True)
    station_state = serializers.CharField(source="station.state", read_only=True)
    station_postal_code = serializers.CharField(source="station.postal_code", read_only=True)
    station_country = serializers.CharField(source="station.country", read_only=True)
    notes = serializers.CharField(source="profile.user.notes", read_only=True)
    # Write fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = TechnicianProfile
        fields = [
            "id",
            "username",
            "password",
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
            'skill_score',
            'total_jobs_completed',
            'total_years_experience',
            'date_joined',
            'notes',
        ]

    def create(self, validated_data):
        # Pop user fields
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        password = validated_data.pop("password", None)  
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            # password=password,
            role=User.Roles.TECHNICIAN,
        )
        user.set_password(password) 
        user.save()

        profile = user.profile

        technician = TechnicianProfile.objects.create(
            profile=profile,
            **validated_data
        )
        return technician    
    
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
