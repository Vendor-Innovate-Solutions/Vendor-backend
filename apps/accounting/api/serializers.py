"""
DRF serializers for accounting models.
"""
from rest_framework import serializers
from apps.accounting.models import Ledger, AccountGroup, LedgerBalance
from apps.company.models import FinancialYear


class AccountGroupSerializer(serializers.ModelSerializer):
    """Serializer for AccountGroup model."""
    
    class Meta:
        model = AccountGroup
        fields = [
            'id', 'name', 'code', 'parent', 'nature',
            'report_type', 'path', 'created_at', 'last_updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_updated_at']


class LedgerSerializer(serializers.ModelSerializer):
    """Serializer for Ledger model."""
    
    group_name = serializers.CharField(source='group.name', read_only=True)
    group_nature = serializers.CharField(source='group.nature', read_only=True)
    
    class Meta:
        model = Ledger
        fields = [
            'id', 'name', 'group', 'group_name', 'group_nature',
            'opening_balance', 'opening_balance_type', 'is_active',
            'created_at', 'last_updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_updated_at']


class LedgerDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Ledger with nested group info."""
    
    group = AccountGroupSerializer(read_only=True)
    
    class Meta:
        model = Ledger
        fields = [
            'id', 'name', 'group', 'opening_balance',
            'opening_balance_type', 'is_active',
            'created_at', 'last_updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_updated_at']


class FinancialYearSerializer(serializers.ModelSerializer):
    """Serializer for FinancialYear model."""
    
    class Meta:
        model = FinancialYear
        fields = [
            'id', 'name', 'start_date', 'end_date',
            'is_closed', 'created_at', 'last_updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'last_updated_at']


class LedgerBalanceSerializer(serializers.ModelSerializer):
    """Serializer for LedgerBalance model."""
    
    ledger_name = serializers.CharField(source='ledger.name', read_only=True)
    financial_year_name = serializers.CharField(source='financial_year.name', read_only=True)
    
    # Calculate DR/CR from balance
    balance_dr = serializers.SerializerMethodField()
    balance_cr = serializers.SerializerMethodField()
    
    class Meta:
        model = LedgerBalance
        fields = [
            'id', 'ledger', 'ledger_name', 'financial_year',
            'financial_year_name', 'opening_balance', 'balance',
            'balance_dr', 'balance_cr', 'last_updated_at'
        ]
        read_only_fields = ['id', 'last_updated_at']
    
    def get_balance_dr(self, obj):
        """Return debit balance or 0."""
        return float(obj.balance) if obj.balance > 0 else 0.0
    
    def get_balance_cr(self, obj):
        """Return credit balance or 0."""
        return float(abs(obj.balance)) if obj.balance < 0 else 0.0
