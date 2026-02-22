from django.shortcuts import render
from .models import *
from .serializers import StaffProfileSerializer
from rest_framework import viewsets, status
from rest_framework.response import Response
# Create your views here.

class StaffProfileViewSet(viewsets.ModelViewSet):
    queryset = StaffProfile.objects.all()
    serializer_class = StaffProfileSerializer