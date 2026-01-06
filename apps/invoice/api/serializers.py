"""
Invoice API serializers.
Handles invoice input/output marshaling for REST APIs.
"""
from rest_framework import serializers
from apps.invoice.models import Invoice, InvoiceLine


class InvoiceLineSerializer(serializers.ModelSerializer):
    """Serializer for invoice line items."""
    
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    uom_name = serializers.CharField(source='uom.name', read_only=True)
    
    class Meta:
        model = InvoiceLine
        fields = [
            'id', 'line_no', 'item', 'item_name', 'item_sku',
            'description', 'quantity', 'unit_rate', 'uom', 'uom_name',
            'discount_pct', 'line_total', 'tax_amount'
        ]
        read_only_fields = ['id', 'line_total', 'tax_amount']


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice with nested lines."""
    
    lines = InvoiceLineSerializer(many=True, read_only=True)
    party_name = serializers.CharField(source='party.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    sales_order_number = serializers.CharField(source='sales_order.order_number', read_only=True, allow_null=True)
    purchase_order_number = serializers.CharField(source='purchase_order.order_number', read_only=True, allow_null=True)
    voucher_number = serializers.CharField(source='voucher.voucher_number', read_only=True, allow_null=True)
    outstanding_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date',
            'party', 'party_name', 'invoice_type', 'status',
            'currency', 'currency_code',
            'sales_order', 'sales_order_number',
            'purchase_order', 'purchase_order_number',
            'voucher', 'voucher_number',
            'total_value', 'amount_received', 'outstanding_amount',
            'shipping_address', 'billing_address',
            'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'company', 'voucher',
            'total_value', 'amount_received', 'created_at', 'updated_at'
        ]
    
    def get_outstanding_amount(self, obj):
        """Calculate outstanding amount (total - received)."""
        return obj.total_value - obj.amount_received


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing invoices."""
    
    party_name = serializers.CharField(source='party.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    outstanding_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'due_date',
            'party_name', 'invoice_type', 'status',
            'currency_code', 'total_value', 'amount_received',
            'outstanding_amount', 'created_at'
        ]
    
    def get_outstanding_amount(self, obj):
        """Calculate outstanding amount (total - received)."""
        return obj.total_value - obj.amount_received


class CreateInvoiceFromOrderSerializer(serializers.Serializer):
    """Serializer for creating invoice from sales order."""
    
    partial_allowed = serializers.BooleanField(default=False, required=False)
    apply_gst = serializers.BooleanField(default=True, required=False)
    company_state_code = serializers.CharField(max_length=5, required=False, allow_blank=True)
