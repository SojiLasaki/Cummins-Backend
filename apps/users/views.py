from rest_framework import viewsets, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from .serializers import AdminUserProfileSerializer, ProfileSerializer, StatioinSerializer, RegionSerializer
from .models import AdminUserProfile, Profile, Station, Region

User = get_user_model()

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

class AdminUserProfileViewSet(viewsets.ModelViewSet):
    queryset = AdminUserProfile.objects.all()
    serializer_class = AdminUserProfileSerializer

class StationViewSet(viewsets.ModelViewSet):
    queryset = Station.objects.all()
    serializer_class = StatioinSerializer

class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer