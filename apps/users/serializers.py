from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Profile, AdminUserProfile, Station, Region
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


def _format_location(city, state):
    """Format location as 'City, State' (skips empty parts)."""
    parts = [p for p in (city or "", state or "") if p]
    return ", ".join(parts) if parts else ""


def _user_profile_payload(user):
    """Build frontend-ready user + profile dict for JWT login response for all roles."""
    profile = getattr(user, "profile", None)
    payload = {
        "id": user.pk,
        "username": user.username,
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "role": user.role,
    }
    if profile:
        payload["profile_id"] = str(profile.id)
        payload["phone_number"] = profile.phone_number or ""
        payload["street_address"] = profile.street_address or ""
        payload["street_address_2"] = profile.street_address_2 or ""
        payload["city"] = profile.city or ""
        payload["state"] = profile.state or ""
        payload["postal_code"] = profile.postal_code or ""
        payload["country"] = profile.country or ""
        payload["notes"] = profile.notes or ""
    else:
        payload["profile_id"] = None
        payload["phone_number"] = ""
        payload["street_address"] = ""
        payload["street_address_2"] = ""
        payload["city"] = ""
        payload["state"] = ""
        payload["postal_code"] = ""
        payload["country"] = ""
        payload["notes"] = ""

    # Station and location: same keys for all roles; meaning depends on role
    payload["station"] = None
    payload["station_name"] = ""
    payload["station_city"] = ""
    payload["station_state"] = ""
    payload["location"] = ""
    payload["specialization"] = ""
    payload["expertise"] = ""

    if not profile:
        return payload

    # Technician: station from TechnicianProfile; location = station city, state
    if user.role == "technician":
        from apps.technicians.models import TechnicianProfile
        tech = TechnicianProfile.objects.filter(profile=profile).select_related("station").first()
        if tech:
            payload["specialization"] = tech.specialization or ""
            payload["expertise"] = tech.expertise or ""
            if tech.station:
                payload["station"] = str(tech.station.id)
                payload["station_name"] = tech.station.name or ""
                payload["station_city"] = tech.station.city or ""
                payload["station_state"] = tech.station.state or ""
                payload["location"] = _format_location(tech.station.city, tech.station.state)
        if not payload["location"]:
            payload["location"] = _format_location(payload["city"], payload["state"])
        return payload

    # Admin: station from AdminUserProfile; location = station city, state
    if user.role == "admin":
        admin = AdminUserProfile.objects.filter(profile=profile).select_related("station").first()
        if admin and admin.station:
            payload["station"] = str(admin.station.id)
            payload["station_name"] = admin.station.name or ""
            payload["station_city"] = admin.station.city or ""
            payload["station_state"] = admin.station.state or ""
            payload["location"] = _format_location(admin.station.city, admin.station.state)
        if not payload["location"]:
            payload["location"] = _format_location(payload["city"], payload["state"])
        return payload

    # Customer (and any other role): location = profile city, state
    payload["location"] = _format_location(payload["city"], payload["state"])
    return payload


class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = _user_profile_payload(user)
        data["role"] = user.role
        data["username"] = user.username
        return data


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


class ProfileSerializer(serializers.ModelSerializer):
    # Include related User info
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "street_address",
            "street_address_2",
            "city",
            "state",
            "postal_code",
            "country",
            "notes",
        ]
        read_only_fields = fields  # everything is read-only


class AdminUserProfileSerializer(serializers.ModelSerializer):
    # Read-only user fields
    id = serializers.CharField(source="profile.id", read_only=True)
    username_display = serializers.CharField(source="profile.user.username", read_only=True)
    email_display = serializers.EmailField(source="profile.user.email", read_only=True)
    phone_number = serializers.CharField(source="profile.user.phone_number", read_only=True)
    first_name_display = serializers.CharField(source="profile.user.first_name", read_only=True)
    last_name_display = serializers.CharField(source="profile.user.last_name", read_only=True)
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(source="profile.user.role", read_only=True)
    street_address = serializers.CharField(source="profile.street_address")
    street_address_2 = serializers.CharField(source="profile.street_address_2")
    city = serializers.CharField(source="profile.city")
    state = serializers.CharField(source="profile.state")
    postal_code = serializers.CharField(source="profile.postal_code")
    country = serializers.CharField(source="profile.country")
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
        model = AdminUserProfile
        fields = [
            "id",
            # 'profile',
            "username",
            'password',
            "email",
            'phone_number',
            "first_name",
            "last_name",
            "username_display",
            "email_display",
            "first_name_display",
            "last_name_display",
            "phone_number",
            "street_address",
            "street_address_2",
            "city",
            "state",
            "postal_code",
            "country",
            'station',
            'station_name',
            'station_street_address',
            'station_street_address_2',
            'station_city',
            'station_state',
            'station_postal_code',
            'station_country',
            "role",
            'status',
            'notes',
        ]

    def create(self, validated_data):
        # Pop user fields
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            # password=password,
            role=User.Roles.ADMIN,
        )
        user.set_password(password) 
        user.save()

        profile = user.profile

        admin = AdminUserProfile.objects.create(
            profile=profile,
            **validated_data
        )
        return admin    
        # Create AdminUserProfile directly
        # profile = AdminUserProfile.objects.create(
        #     user=user,
        #     **validated_data  # now only profile fields like notes, phone_number
        # )
    
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
    

class StatioinSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    class Meta:
        model = Station
        fields = [
            "id",
            "name",
            "region",
            "region_name",
            'street_address',
            'street_address_2',
            'city',
            'state',
            'postal_code',
            'country',
            'is_active',
            'created_at',
        ]


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = "__all__"