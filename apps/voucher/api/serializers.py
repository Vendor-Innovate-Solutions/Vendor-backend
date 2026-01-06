"""
Payment API serializers.
Handles payment and payment line serialization for REST APIs.
"""
from rest_framework import serializers
from apps.voucher.models import Payment, PaymentLine


class PaymentLineSerializer(serializers.ModelSerializer):
    """Serializer for payment allocation lines."""
    
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_party = serializers.CharField(source='invoice.party.name', read_only=True)
    invoice_total = serializers.DecimalField(
        source='invoice.total_value',
        max_digits=16,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = PaymentLine
        fields = [
            'id', 'invoice', 'invoice_number', 'invoice_party',
            'invoice_total', 'amount_applied', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment with nested allocations."""
    
    lines = PaymentLineSerializer(many=True, read_only=True)
    party_name = serializers.CharField(source='party.name', read_only=True)
    bank_account_name = serializers.CharField(source='bank_account.name', read_only=True)
    voucher_number = serializers.CharField(source='voucher.voucher_number', read_only=True)
    payment_type = serializers.CharField(source='voucher.voucher_type.code', read_only=True)
    total_allocated = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'voucher', 'voucher_number', 'payment_type',
            'party', 'party_name', 'bank_account', 'bank_account_name',
            'payment_date', 'payment_mode', 'reference_number',
            'status', 'notes', 'total_allocated', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'voucher', 'status', 'created_at', 'updated_at'
        ]
    
    def get_total_allocated(self, obj):
        """Calculate total amount allocated."""
        from django.db.models import Sum
        total = obj.lines.aggregate(total=Sum('amount_applied'))['total']
        return total or '0.00'


class PaymentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing payments."""
    
    party_name = serializers.CharField(source='party.name', read_only=True)
    voucher_number = serializers.CharField(source='voucher.voucher_number', read_only=True)
    payment_type = serializers.CharField(source='voucher.voucher_type.code', read_only=True)
    total_allocated = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'voucher_number', 'payment_type', 'party_name',
            'payment_date', 'payment_mode', 'status',
            'total_allocated', 'created_at'
        ]
    
    def get_total_allocated(self, obj):
        """Calculate total amount allocated."""
        from django.db.models import Sum
        total = obj.lines.aggregate(total=Sum('amount_applied'))['total']
        return total or '0.00'


class CreatePaymentSerializer(serializers.Serializer):
    """Serializer for creating a new payment."""
    
    party_id = serializers.UUIDField()
    bank_account_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=['PAYMENT', 'RECEIPT'])
    payment_date = serializers.DateField(required=False, allow_null=True)
    payment_mode = serializers.ChoiceField(
        choices=['CASH', 'CHEQUE', 'BANK_TRANSFER', 'UPI', 'CARD', 'OTHER'],
        default='CASH',
        required=False
    )
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class AllocatePaymentSerializer(serializers.Serializer):
    """Serializer for allocating payment to invoice."""
    
    invoice_id = serializers.UUIDField()
    amount_applied = serializers.DecimalField(max_digits=16, decimal_places=2)
