from django.shortcuts import render
from rest_framework import viewsets
from .models import ActivityLog
from .serializers import ActivityLogSerializer
# Create your views here.

class ActivityLogViewSet(viewsets.ModelViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer