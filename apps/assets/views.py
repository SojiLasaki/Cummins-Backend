from django.shortcuts import render
from .models import Asset
from .serializers import AssetSerializer
from rest_framework import viewsets
# Create your views here.

class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer