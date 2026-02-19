from django.shortcuts import render
from rest_framework import viewsets
from .models import CustomerProfile
from .serializers import CustomerProfileSerializer
# Create your views here.

class CustomerProfileViewSet(viewsets.ModelViewSet):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer