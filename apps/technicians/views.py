from django.shortcuts import render
from rest_framework import viewsets
from .models import TechnicianProfile
from .serializers import TechnicianProfileSerializer
# Create your views here.

class TechnicianProfileViewSet(viewsets.ModelViewSet):
    queryset = TechnicianProfile.objects.all()
    serializer_class = TechnicianProfileSerializer