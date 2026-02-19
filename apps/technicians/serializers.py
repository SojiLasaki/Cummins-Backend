from rest_framework import serializers
from .models import TechnicianProfile

class TechnicianProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianProfile
        fields = '__all__'
