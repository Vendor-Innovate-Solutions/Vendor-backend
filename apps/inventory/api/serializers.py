"""
Inventory API serializers.
DRF serializers for stock items, movements, and reservations.
"""
from rest_framework import serializers
from apps.inventory.models import (
    StockItem, StockMovement, StockReservation, StockBalance,
    Godown, StockGroup, StockCategory
)


class GodownSerializer(serializers.ModelSerializer):
    """Serializer for Godown (warehouse/location)."""
    
    class Meta:
        model = Godown
        fields = ['id', 'name', 'code', 'godown_type', 'is_active']
        read_only_fields = ['id']


class StockGroupSerializer(serializers.ModelSerializer):
    """Serializer for StockGroup."""
    
    class Meta:
        model = StockGroup
        fields = ['id', 'name', 'code', 'parent', 'is_active']
        read_only_fields = ['id', 'company']


class StockCategorySerializer(serializers.ModelSerializer):
    """Serializer for StockCategory."""
    
    class Meta:
        model = StockCategory
        fields = ['id', 'name', 'code', 'is_active']
        read_only_fields = ['id', 'company']


class StockItemSerializer(serializers.ModelSerializer):
    """Serializer for StockItem with nested relations."""
    
    group_name = serializers.CharField(source='group.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    uom_name = serializers.CharField(source='base_uom.name', read_only=True)
    
    class Meta:
        model = StockItem
        fields = [
            'id', 'name', 'sku', 'barcode', 'description',
            'group', 'group_name',
            'category', 'category_name',
            'base_uom', 'uom_name',
            'opening_stock', 'opening_rate',
            'reorder_level', 'reorder_quantity',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class StockItemListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing stock items."""
    
    group_name = serializers.CharField(source='group.name', read_only=True)
    uom_name = serializers.CharField(source='base_uom.name', read_only=True)
    
    class Meta:
        model = StockItem
        fields = [
            'id', 'name', 'sku', 'group_name', 'uom_name', 'is_active'
        ]


class StockBalanceSerializer(serializers.ModelSerializer):
    """Serializer for StockBalance."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    godown_name = serializers.CharField(source='godown.name', read_only=True)
    uom = serializers.CharField(source='item.base_uom.name', read_only=True)
    
    class Meta:
        model = StockBalance
        fields = [
            'id', 'item', 'item_name', 'item_sku',
            'godown', 'godown_name',
            'batch', 'quantity', 'uom',
            'updated_at'
        ]
        read_only_fields = ['id', 'company', 'updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    from_godown_name = serializers.CharField(source='from_godown.name', read_only=True)
    to_godown_name = serializers.CharField(source='to_godown.name', read_only=True)
    total_value = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    
    def get_total_value(self, obj):
        """Calculate total value (quantity * rate)."""
        return obj.quantity * obj.rate
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'item', 'item_name',
            'movement_type', 'quantity', 'rate', 'total_value',
            'from_godown', 'from_godown_name',
            'to_godown', 'to_godown_name',
            'batch', 'reason', 'date',
            'reference_type', 'reference_id',
            'created_at'
        ]
        read_only_fields = ['id', 'company', 'created_at']


class StockMovementCreateSerializer(serializers.Serializer):
    """Serializer for creating stock movements."""
    
    item_id = serializers.UUIDField()
    godown_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    movement_type = serializers.ChoiceField(choices=['IN', 'OUT'])
    rate = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    batch = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    reference_type = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    reference_id = serializers.UUIDField(required=False, allow_null=True)


class StockTransferSerializer(serializers.Serializer):
    """Serializer for stock transfers between godowns."""
    
    item_id = serializers.UUIDField()
    from_godown_id = serializers.UUIDField()
    to_godown_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    rate = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    batch = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)


class StockReservationSerializer(serializers.ModelSerializer):
    """Serializer for StockReservation."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    godown_name = serializers.CharField(source='godown.name', read_only=True)
    
    class Meta:
        model = StockReservation
        fields = [
            'id', 'item', 'item_name',
            'godown', 'godown_name',
            'quantity', 'status',
            'reserved_for_type', 'reserved_for_id',
            'expires_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class StockSummarySerializer(serializers.Serializer):
    """Serializer for stock summary/report data."""
    
    item_id = serializers.UUIDField()
    item_name = serializers.CharField()
    total_quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    by_godown = serializers.ListField(child=serializers.DictField())
