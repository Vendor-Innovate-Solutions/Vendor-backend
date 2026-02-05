"""
Order API serializers.
Lightweight input/output marshaling for order operations.
"""
from rest_framework import serializers
from apps.orders.models import SalesOrder, PurchaseOrder, OrderItem
from apps.party.models import Party
from apps.company.models import Currency
from apps.inventory.models import PriceList, StockItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order line items."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    uom_name = serializers.CharField(source='uom.name', read_only=True)
    line_total = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'item', 'item_name', 'item_sku',
            'quantity', 'unit_rate', 'uom', 'uom_name',
            'discount_percent', 'discount_amount',
            'tax_rate', 'tax_amount',
            'line_total', 'notes'
        ]
        read_only_fields = ['id', 'line_total']


class SalesOrderSerializer(serializers.ModelSerializer):
    """Serializer for SalesOrder with nested items."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True, source='orderitem_set')
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    assigned_employee_id = serializers.UUIDField(source='assigned_employee.id', read_only=True, allow_null=True)
    assigned_employee_name = serializers.CharField(source='assigned_employee.name', read_only=True, allow_null=True)
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_number', 'customer', 'customer_name',
            'currency', 'currency_code', 'price_list',
            'status', 'order_date', 'delivery_date',
            'customer_po_number', 'terms_and_conditions', 'notes',
            'total_amount', 'items',
            'assigned_employee_id', 'assigned_employee_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'company', 'total_amount', 'created_at', 'updated_at']


class SalesOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing sales orders."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    assigned_employee_id = serializers.UUIDField(source='assigned_employee.id', read_only=True, allow_null=True)
    assigned_employee_name = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_number', 'customer_name',
            'currency_code', 'status', 'order_date', 'delivery_date',
            'item_count', 'assigned_employee_id', 'assigned_employee_name',
            'created_at'
        ]
    
    def get_assigned_employee_name(self, obj):
        if obj.assigned_employee:
            return obj.assigned_employee.name
        return None


class CreateSalesOrderSerializer(serializers.Serializer):
    """Serializer for creating a new sales order."""
    
    customer_id = serializers.UUIDField()
    currency_id = serializers.UUIDField()
    price_list_id = serializers.UUIDField(required=False, allow_null=True)
    order_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    shipping_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    billing_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_terms = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class AddOrderItemSerializer(serializers.Serializer):
    """Serializer for adding an item to an order."""
    
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3)
    override_rate = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    uom_id = serializers.UUIDField(required=False, allow_null=True)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class UpdateOrderItemSerializer(serializers.Serializer):
    """Serializer for updating an order item."""
    
    quantity = serializers.DecimalField(max_digits=15, decimal_places=3, required=False)
    unit_rate = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CancelOrderSerializer(serializers.Serializer):
    """Serializer for cancelling an order."""
    
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """Serializer for PurchaseOrder with nested items."""
    
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True, source='orderitem_set')
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'supplier', 'supplier_name',
            'currency', 'currency_code', 'price_list',
            'status', 'order_date', 'due_date', 'delivery_date',
            'shipping_address', 'billing_address',
            'payment_terms', 'notes',
            'total_amount', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'company', 'total_amount', 'created_at', 'updated_at']


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing purchase orders."""
    
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_number', 'supplier_name',
            'currency_code', 'status', 'order_date', 'due_date',
            'item_count', 'created_at'
        ]


class CreatePurchaseOrderSerializer(serializers.Serializer):
    """Serializer for creating a new purchase order."""
    
    supplier_id = serializers.UUIDField()
    currency_id = serializers.UUIDField()
    price_list_id = serializers.UUIDField(required=False, allow_null=True)
    order_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    shipping_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    billing_address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_terms = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
