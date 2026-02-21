from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomerProfile

# class CustomerProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomerProfile
#         fields = '__all__'
User = get_user_model()

class CustomerProfileSerializer(serializers.ModelSerializer):
    # username = serializers.CharField(write_only=True)
    # email = serializers.EmailField(write_only=True)
    # first_name = serializers.CharField(write_only=True)
    # last_name = serializers.CharField(write_only=True)

    # # READ (returned from related user)
    # user_username = serializers.CharField(source="user.username", read_only=True)
    # user_email = serializers.EmailField(source="user.email", read_only=True)
    # user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    # user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    class Meta:
        model = CustomerProfile
        fields = [
            "id",
            # write-only
            "username",
            "email",
            "first_name",
            "last_name",

            # # read-only
            # "user_username",
            # "user_email",
            # "user_first_name",
            # "user_last_name",

            'company_name',
            "phone_number",
            "street_address",
            "city",
            "state",
            "postal_code",
            "country",
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
            role=User.Roles.CUSTOMER
        )

        # Create profile
        profile = CustomerProfile.objects.create(
            user=user,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=User.Roles.CUSTOMER
            **validated_data
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