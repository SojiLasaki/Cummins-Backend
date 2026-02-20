from rest_framework import serializers
from .models import Manual, Component, Tag, Image
from apps.inventory.serializers import ComponentSerializer
# class ComponentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Component
#         fields = '__all__'

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = '__all__'

class ManualSerializer(serializers.ModelSerializer):
    component = ComponentSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    images = ImageSerializer(many=True, read_only=True)

    class Meta:
        model = Manual
        fields = '__all__'