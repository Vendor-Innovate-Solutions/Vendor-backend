"""
Company API Serializers
"""
from rest_framework import serializers
from apps.company.models import Company, Currency, Address


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model"""
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'decimal_places']
        read_only_fields = ['id']


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model"""
    class Meta:
        model = Address
        fields = [
            'id', 'address_type', 'line1', 'line2', 'city', 
            'state', 'country', 'pincode'
        ]
        read_only_fields = ['id']


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model"""
    base_currency_code = serializers.CharField(source='base_currency.code', read_only=True)
    base_currency_name = serializers.CharField(source='base_currency.name', read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id', 'code', 'name', 'legal_name', 'company_type',
            'timezone', 'language', 'base_currency', 'base_currency_code',
            'base_currency_name', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a Company"""
    base_currency_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Company
        fields = [
            'code', 'name', 'legal_name', 'company_type',
            'timezone', 'language', 'base_currency_id', 'is_active'
        ]
    
    def validate_code(self, value):
        """Validate company code is unique"""
        if Company.objects.filter(code=value).exists():
            raise serializers.ValidationError("Company with this code already exists.")
        return value.upper()
    
    def validate_base_currency_id(self, value):
        """Validate currency exists"""
        if not Currency.objects.filter(id=value).exists():
            raise serializers.ValidationError("Currency does not exist.")
        return value
    
    def create(self, validated_data):
        """Create company with currency"""
        currency_id = validated_data.pop('base_currency_id')
        currency = Currency.objects.get(id=currency_id)
        validated_data['base_currency'] = currency
        return super().create(validated_data)
