from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomerProfile

# class CustomerProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomerProfile
#         fields = '__all__'
User = get_user_model()

class CustomerProfileSerializer(serializers.ModelSerializer):
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
            password=User.objects.make_random_password()
        )

        # Create profile
        profile = CustomerProfile.objects.create(
            user=user,
            **validated_data
        )

        return profile