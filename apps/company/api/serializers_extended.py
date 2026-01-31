"""
Extended Company API Serializers for Setup Phases
"""
from rest_framework import serializers
from apps.company.models import Company, Currency, Address, CompanyFeature


class CompanyFeatureSerializer(serializers.ModelSerializer):
    """Serializer for CompanyFeature model"""
    class Meta:
        model = CompanyFeature
        fields = [
            'id', 'company', 'inventory_enabled', 'accounting_enabled',
            'payroll_enabled', 'gst_enabled', 'locked',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class AddressCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Address (PHASE 3)"""
    class Meta:
        model = Address
        fields = [
            'address_type', 'line1', 'line2', 'city', 
            'state', 'country', 'pincode'
        ]
    
    def validate(self, data):
        """Ensure required fields are present"""
        required_fields = ['line1', 'city', 'state', 'country', 'pincode']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError(f"{field.replace('_', ' ').title()} is required")
        return data


class AddressDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Address with company info"""
    company_name = serializers.CharField(source='company.name', read_only=True)
    address_type_display = serializers.CharField(source='get_address_type_display', read_only=True)
    
    class Meta:
        model = Address
        fields = [
            'id', 'company', 'company_name', 'address_type', 
            'address_type_display', 'line1', 'line2', 'city', 
            'state', 'country', 'pincode', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class CompanyBusinessSettingsSerializer(serializers.Serializer):
    """PHASE 2: Update company business settings and module toggles"""
    # Company settings
    timezone = serializers.CharField(max_length=50, required=False)
    language = serializers.CharField(max_length=20, required=False)
    base_currency_id = serializers.UUIDField(required=False)
    
    # Module toggles (CompanyFeature)
    inventory_enabled = serializers.BooleanField(required=False)
    accounting_enabled = serializers.BooleanField(required=False)
    payroll_enabled = serializers.BooleanField(required=False)
    gst_enabled = serializers.BooleanField(required=False)
    
    def validate_base_currency_id(self, value):
        """Validate currency exists"""
        if value and not Currency.objects.filter(id=value).exists():
            raise serializers.ValidationError("Currency does not exist")
        return value
    
    def update_company_settings(self, company):
        """Update company and features with validated data"""
        # Update company fields
        if 'timezone' in self.validated_data:
            company.timezone = self.validated_data['timezone']
        if 'language' in self.validated_data:
            company.language = self.validated_data['language']
        if 'base_currency_id' in self.validated_data:
            currency = Currency.objects.get(id=self.validated_data['base_currency_id'])
            company.base_currency = currency
        company.save()
        
        # Update or create company features
        features, created = CompanyFeature.objects.get_or_create(company=company)
        if 'inventory_enabled' in self.validated_data:
            features.inventory_enabled = self.validated_data['inventory_enabled']
        if 'accounting_enabled' in self.validated_data:
            features.accounting_enabled = self.validated_data['accounting_enabled']
        if 'payroll_enabled' in self.validated_data:
            features.payroll_enabled = self.validated_data['payroll_enabled']
        if 'gst_enabled' in self.validated_data:
            features.gst_enabled = self.validated_data['gst_enabled']
        features.save()
        
        return company, features


class CompanyDetailedSerializer(serializers.ModelSerializer):
    """Complete company info with features and addresses"""
    base_currency_code = serializers.CharField(source='base_currency.code', read_only=True)
    base_currency_name = serializers.CharField(source='base_currency.name', read_only=True)
    base_currency_symbol = serializers.CharField(source='base_currency.symbol', read_only=True)
    features = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = [
            'id', 'code', 'name', 'legal_name', 'company_type',
            'timezone', 'language', 'base_currency', 'base_currency_code',
            'base_currency_name', 'base_currency_symbol', 'is_active',
            'created_at', 'updated_at', 'features', 'addresses'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_features(self, obj):
        """Get company features"""
        try:
            features = CompanyFeature.objects.get(company=obj)
            return CompanyFeatureSerializer(features).data
        except CompanyFeature.DoesNotExist:
            return None
    
    def get_addresses(self, obj):
        """Get all company addresses"""
        addresses = Address.objects.filter(company=obj).order_by('-created_at')
        return AddressDetailSerializer(addresses, many=True).data


class CompanySetupStatusSerializer(serializers.Serializer):
    """Get setup completion status"""
    phase1_completed = serializers.BooleanField()
    phase2_completed = serializers.BooleanField()
    phase3_completed = serializers.BooleanField()
    setup_percentage = serializers.IntegerField()
    next_step = serializers.CharField()
    company = CompanyDetailedSerializer()
    
    @staticmethod
    def get_setup_status(company):
        """Calculate setup completion"""
        phase1 = company is not None
        phase2 = CompanyFeature.objects.filter(company=company).exists() if company else False
        phase3 = Address.objects.filter(company=company).exists() if company else False
        
        completed = sum([phase1, phase2, phase3])
        percentage = int((completed / 3) * 100)
        
        if not phase2:
            next_step = "Configure business settings and enable modules (PHASE 2)"
        elif not phase3:
            next_step = "Add your registered office address (PHASE 3)"
        else:
            next_step = "Setup complete! Start using your ERP system"
        
        return {
            'phase1_completed': phase1,
            'phase2_completed': phase2,
            'phase3_completed': phase3,
            'setup_percentage': percentage,
            'next_step': next_step,
            'company': CompanyDetailedSerializer(company).data if company else None
        }
