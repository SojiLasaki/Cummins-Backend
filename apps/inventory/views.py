from django.shortcuts import render
from rest_framework import viewsets
from .models import Component, Part, InventoryTransaction
from django.db.models import Count
from .serializers import *
# Create your views here.

class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.annotate(
        parts_count=Count('parts')
    )
    serializer_class = ComponentSerializer

class PartViewSet(viewsets.ModelViewSet):
    queryset = Part.objects.all()
    serializer_class = PartSerializer

class InventoryTransactionViewSet(viewsets.ModelViewSet):
    queryset = InventoryTransaction.objects.all()
    serializer_class = InventoryTransactionSerializer
    