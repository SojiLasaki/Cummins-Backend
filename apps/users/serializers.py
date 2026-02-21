# from django.contrib.auth import get_user_model
# from rest_framework import serializers
# from .models import AdminUserProfile, Profile

# User = get_user_model()
# class ProfileSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(write_only=True)
#     email = serializers.EmailField(write_only=True)
#     first_name = serializers.CharField(write_only=True)
#     last_name = serializers.CharField(write_only=True)

#     class Meta:
#         model = Profile
#         fields = [
#             "id",
#             "username",
#             "email",
#             "first_name",
#             "last_name",
#             "role",
#             "phone_number",
#             "street_address",
#             "street_address_2",
#             "city",
#             "state",
#             "postal_code",
#             "country",
#         ]

#     def create(self, validated_data):
#         username = validated_data.pop("username")
#         email = validated_data.pop("email")
#         first_name = validated_data.pop("first_name")
#         last_name = validated_data.pop("last_name")

#         # Create user FIRST
#         user = User.objects.create_user(
#             username=username,
#             email=email,
#             first_name=first_name,
#             last_name=last_name,
#             password=User.objects.make_random_password(),
#             role=User.Roles.CUSTOMER
#         )

#         # Now create profile with user attached
#         profile = Profile.objects.create(
#             user=user,
#             username=user.username,
#             email=user.email,
#             first_name=user.first_name,
#             last_name=user.last_name,
#             role=User.Roles.CUSTOMER,
#             **validated_data
#         )
#         return profile


# class AdminUserProfileSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(write_only=True)
#     email = serializers.EmailField(write_only=True)
#     first_name = serializers.CharField(write_only=True)
#     last_name = serializers.CharField(write_only=True)

#     class Meta:
#         model = AdminUserProfile
#         fields = [
#             "id",
#             "username",
#             "email",
#             "first_name",
#             "last_name",
#             "phone_number",
#             "role",
#             "street_address",
#             "street_address_2",
#             "city",
#             "state",
#             "postal_code",
#             "country",
#             "notes",
#         ]

#     def create(self, validated_data):
#         username = validated_data.pop("username")
#         email = validated_data.pop("email")
#         first_name = validated_data.pop("first_name")
#         last_name = validated_data.pop("last_name")

#         # Create user
#         user = User.objects.create_user(
#             username=username,
#             email=email,
#             first_name=first_name,
#             last_name=last_name,
#             password=User.objects.make_random_password(),
#             role=User.Roles.ADMIN  
#         )

#         # Create profile
#         profile = AdminUserProfile.objects.create(
#             user=user,
#             username=user.username,
#             email=user.email,
#             first_name=user.first_name,
#             last_name=user.last_name,
#             role=user.Roles.ADMIN,  
#             **validated_data
#         )

#         return profile


    
# from django.contrib.auth import get_user_model
# from rest_framework import serializers
# from .models import Profile, AdminUserProfile

# User = get_user_model()


# class ProfileSerializer(serializers.ModelSerializer):
#     # Read fields (returned to frontend)
#     username_display = serializers.CharField(source="user.username", read_only=True)
#     email_display = serializers.EmailField(source="user.email", read_only=True)
#     first_name_display = serializers.CharField(source="user.first_name", read_only=True)
#     last_name_display = serializers.CharField(source="user.last_name", read_only=True)
#     role = serializers.CharField(source="user.role", read_only=True)

#     # Write fields (used during creation)
#     username = serializers.CharField(write_only=True)
#     email = serializers.EmailField(write_only=True)
#     first_name = serializers.CharField(write_only=True)
#     last_name = serializers.CharField(write_only=True)

#     class Meta:
#         model = Profile
#         fields = [
#             "id",

#             # Returned fields
#             "username_display",
#             "email_display",
#             "first_name_display",
#             "last_name_display",
#             "role",

#             # Write fields
#             "username",
#             "email",
#             "first_name",
#             "last_name",

#             # Profile fields
#             "phone_number",
#             "street_address",
#             "city",
#             "state",
#             "postal_code",
#             "country",
#         ]

#     def create_user_and_profile(self, validated_data, role):
#         # Use pop with default to prevent KeyError
#         username = validated_data.pop("username", None)
#         email = validated_data.pop("email", None)
#         first_name = validated_data.pop("first_name", "")
#         last_name = validated_data.pop("last_name", "")

#         if not username or not email:
#             raise serializers.ValidationError("Username and email are required.")

#         user = User.objects.create_user(
#             username=username,
#             email=email,
#             first_name=first_name,
#             last_name=last_name,
#             password=User.objects.make_random_password(),
#             role=role,
#         )

#         profile = Profile.objects.create(
#             user=user,
#             **validated_data
#         )

#         return profile


# class AdminUserProfileSerializer(ProfileSerializer):
#     class Meta(ProfileSerializer.Meta):
#         model = AdminUserProfile
#         fields = AdminUserProfileSerializer.Meta.fields + ["notes"]

#     def create(self, validated_data):
#         return self.create_user_and_profile(validated_data, User.Roles.ADMIN)




    
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Profile, AdminUserProfile

User = get_user_model()

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
            "notes",
        ]

    def create(self, validated_data):
        # Pop user fields
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=User.objects.make_random_password(),
            role=User.Roles.ADMIN,
        )

        # Create AdminUserProfile directly
        profile = AdminUserProfile.objects.create(
            user=user,
            **validated_data  # now only profile fields like notes, phone_number
        )

        return profile