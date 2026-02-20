from django.shortcuts import render
from rest_framework import viewsets
from .models import Manual, Component, Tag, Image
from .serializers import ManualSerializer, ComponentSerializer, TagSerializer, ImageSerializer
# Create your views here.

class ManualViewSet(viewsets.ModelViewSet):
    queryset = Manual.objects.all()
    serializer_class = ManualSerializer

class ComponentViewSet(viewsets.ModelViewSet):
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer

class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
