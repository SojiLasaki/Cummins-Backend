from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Profile, AdminUserProfile, Station, Region
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["username"] = self.user.username
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
    username_display = serializers.CharField(source="user.username", read_only=True)
    email_display = serializers.EmailField(source="user.email", read_only=True)
    first_name_display = serializers.CharField(source="user.first_name", read_only=True)
    last_name_display = serializers.CharField(source="user.last_name", read_only=True)
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(source="user.role", read_only=True)

    # Write fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)

    class Meta:
        model = AdminUserProfile
        fields = [
            "id",
            'profile',
            "username",
            "email",
            "first_name",
            "last_name",
            "username_display",
            "email_display",
            "first_name_display",
            "last_name_display",
            "role",
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
            password=password,
            role=User.Roles.ADMIN,
        )

        # Create AdminUserProfile directly
        profile = AdminUserProfile.objects.create(
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