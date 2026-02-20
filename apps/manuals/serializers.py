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
    component = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    images = ImageSerializer(many=True, read_only=True)
    created_by = serializers.CharField(source='created_by.get_full_name', read_only=True)
   
    class Meta:
        model = Manual
        fields = '__all__'

    def get_component(self, obj):
        return [c.name for c in obj.component.all()]

    def get_tags(self, obj):
        return [t.name for t in obj.tags.all()]
    