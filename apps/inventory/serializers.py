from rest_framework import serializers
from .models import Component, Part, InventoryTransaction

class ComponentSerializer(serializers.ModelSerializer):
    parts_count = serializers.IntegerField(read_only=True)
    class Meta:
        model = Component
        fields = '__all__'


class PartSerializer(serializers.ModelSerializer):
    components = serializers.SerializerMethodField()
    components_id = serializers.PrimaryKeyRelatedField(many=True, read_only=True, source='components')

    class Meta:
        model = Part
        fields = [
            'id',
            'part_number',
            'name',
            'description',
            'quantity_available',
            'reorder_threshold',
            'category',
            'weight_kg',
            'cost_price',
            'resale_price',
            'status',
            'supplier',
            'inventory_deducted',
            'created_at',
            'components', 
            'last_ordered_at',
            'components_id',
        ]

    def get_components(self, obj):
        # Return only the names of related components
        return [c.name for c in obj.components.all()]
    

class InventoryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransaction
        fields = '__all__'