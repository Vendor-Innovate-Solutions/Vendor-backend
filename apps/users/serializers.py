"""
User serializers for registration and OTP verification.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.users.models import PhoneOTP
from rest_framework_simplejwt.tokens import RefreshToken
from core.auth.models import UserRole

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Creates a new user with email, phone, and full name.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    phone = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(required=True)
    
    class Meta:
        model = User
        fields = ['email', 'phone', 'full_name', 'password']
    
    def validate(self, data):
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})
        
        if User.objects.filter(phone=data['phone']).exists():
            raise serializers.ValidationError({"phone": "This phone number is already registered."})
        
        return data
    
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            first_name=validated_data.get('full_name', ''),
            password=validated_data['password']
        )
        return user


class SendPhoneOTPSerializer(serializers.Serializer):
    """
    Serializer for sending OTP to phone number.
    """
    phone = serializers.CharField(max_length=20)
    
    def validate_phone(self, value):
        # Ensure phone number format starts with +
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must include country code (e.g., +1)")
        return value


class VerifyPhoneOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying phone OTP.
    """
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for returning user details.
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'full_name', 'phone_verified', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class UserLoginResponseSerializer(serializers.Serializer):
    """
    Serializer for user login response.
    """
    user = UserDetailSerializer()
    access = serializers.CharField()
    refresh = serializers.CharField()


class RoleSelectionSerializer(serializers.Serializer):
    """
    Serializer for user role selection during onboarding.
    """
    role = serializers.ChoiceField(choices=UserRole.choices)


class UserContextSerializer(serializers.Serializer):
    """
    Serializer for user context resolution (GET /me/context).
    Returns user's role, companies, and default company.
    """
    user_id = serializers.CharField(source='id')
    email = serializers.EmailField()
    full_name = serializers.SerializerMethodField()
    role = serializers.CharField(source='selected_role')
    role_selected = serializers.SerializerMethodField()
    has_company = serializers.SerializerMethodField()
    companies = serializers.SerializerMethodField()
    default_company = serializers.SerializerMethodField()
    default_company_id = serializers.SerializerMethodField()
    is_internal_user = serializers.BooleanField()
    is_portal_user = serializers.BooleanField()
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_role_selected(self, obj):
        return obj.selected_role is not None
    
    def get_has_company(self, obj):
        return obj.company_memberships.filter(is_active=True).exists()
    
    def get_companies(self, obj):
        """Get all companies user belongs to"""
        companies = obj.company_memberships.filter(is_active=True).select_related('company')
        return [
            {
                'id': str(cm.company.id),
                'name': cm.company.name,
                'code': cm.company.code,
                'role': cm.role,
                'is_default': cm.is_default
            }
            for cm in companies
        ]
    
    def get_default_company(self, obj):
        """Get default company"""
        try:
            default_cm = obj.company_memberships.filter(
                is_active=True,
                is_default=True
            ).select_related('company').first()
            if default_cm:
                return {
                    'id': str(default_cm.company.id),
                    'name': default_cm.company.name,
                    'code': default_cm.company.code,
                    'role': default_cm.role
                }
        except:
            pass
        return None
    
    def get_default_company_id(self, obj):
        """Get default company ID"""
        try:
            default_cm = obj.company_memberships.filter(
                is_active=True,
                is_default=True
            ).first()
            if default_cm:
                return str(default_cm.company.id)
        except:
            pass
        return None
