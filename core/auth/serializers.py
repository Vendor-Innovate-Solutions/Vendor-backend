"""
Custom JWT serializers with ERP-specific claims.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ERPTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that:
    - Uses email instead of username for login
    - Includes ERP-specific claims:
      - username, email
      - active_company (current company context)
      - roles (all CompanyUser roles for this user)
      - is_internal_user / is_portal_user flags
    
    Frontend can use these claims to:
    - Display active company
    - Show/hide features based on roles
    - Route to correct dashboard (internal vs retailer)
    """
    # Override username_field to use email
    username_field = 'email'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field and add email field
        self.fields.pop('username', None)
        self.fields['email'] = serializers.EmailField(required=True)
    
    def validate(self, attrs):
        """
        Validate using email instead of username.
        """
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Find user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'email': 'No user found with this email address.'
                })
            
            # Check password
            if not user.check_password(password):
                raise serializers.ValidationError({
                    'detail': 'Invalid credentials.'
                })
            
            # Check if user is active
            if not user.is_active:
                raise serializers.ValidationError({
                    'detail': 'User account is disabled.'
                })
            
            # Generate tokens manually since we're bypassing parent validation
            refresh = self.get_token(user)
            
            data = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            
            return data
        
        raise serializers.ValidationError({
            'detail': 'Email and password are required.'
        })
    
    @classmethod
    def get_token(cls, user):
        """
        Add custom claims to JWT token.
        
        Args:
            user: User instance
        
        Returns:
            Token with custom claims
        """
        token = super().get_token(user)
        
        # Basic user info
        token['username'] = user.username
        token['email'] = user.email or ''
        
        # User type flags
        token['is_internal_user'] = getattr(user, 'is_internal_user', False)
        token['is_portal_user'] = getattr(user, 'is_portal_user', False)
        
        # Active company context
        if user.active_company:
            token['active_company'] = {
                'id': str(user.active_company.id),
                'name': user.active_company.name,
                'code': user.active_company.code,
            }
        else:
            token['active_company'] = None
        
        # User roles (for internal users)
        if hasattr(user, 'company_memberships'):
            roles = list(
                user.company_memberships
                .filter(is_active=True)
                .values_list('role', flat=True)
            )
            token['roles'] = roles
        else:
            token['roles'] = []
        
        # Available companies (for company switching)
        if hasattr(user, 'company_memberships'):
            companies = list(
                user.company_memberships
                .filter(is_active=True)
                .values('company__id', 'company__name', 'company__code', 'role')
            )
            token['available_companies'] = [
                {
                    'id': str(c['company__id']),
                    'name': c['company__name'],
                    'code': c['company__code'],
                    'role': c['role'],
                }
                for c in companies
            ]
        else:
            token['available_companies'] = []
        
        # Retailer info (for portal users)
        if hasattr(user, 'retailer_profile'):
            try:
                retailer = user.retailer_profile
                token['retailer'] = {
                    'party_id': str(retailer.party.id),
                    'party_name': retailer.party.name,
                    'can_place_orders': retailer.can_place_orders,
                    'can_view_balance': retailer.can_view_balance,
                }
            except Exception:
                token['retailer'] = None
        else:
            token['retailer'] = None
        
        return token


class LoginOTPRequestSerializer(serializers.Serializer):
    """
    Serializer for Step 1 of OTP-based login.
    Validates email and password, returns session token for OTP verification.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if not email or not password:
            raise serializers.ValidationError({
                'detail': 'Email and password are required.'
            })
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'email': 'No user found with this email address.'
            })
        
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({
                'detail': 'Invalid credentials.'
            })
        
        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'User account is disabled.'
            })
        
        # Check if user has phone number
        if not user.phone:
            raise serializers.ValidationError({
                'phone': 'No phone number associated with this account. Please contact support.'
            })
        
        attrs['user'] = user
        return attrs


class LoginOTPVerifySerializer(serializers.Serializer):
    """
    Serializer for Step 2 of OTP-based login.
    Validates OTP and returns JWT tokens.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value
    
    def validate(self, attrs):
        from apps.users.models import PhoneOTP
        
        email = attrs.get('email')
        otp = attrs.get('otp')
        
        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'email': 'No user found with this email address.'
            })
        
        # Find the latest login OTP for this user
        try:
            phone_otp = PhoneOTP.objects.filter(
                user=user,
                purpose=PhoneOTP.PURPOSE_LOGIN,
                is_verified=False
            ).latest('created_at')
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError({
                'otp': 'No OTP found for this account. Please request a new one.'
            })
        
        # Check if OTP is expired
        if phone_otp.is_expired():
            raise serializers.ValidationError({
                'otp': 'OTP has expired. Please request a new one.'
            })
        
        # Check max attempts
        if phone_otp.attempts >= 3:
            raise serializers.ValidationError({
                'otp': 'Maximum OTP attempts exceeded. Please request a new OTP.'
            })
        
        # Validate OTP
        if phone_otp.otp != otp:
            phone_otp.attempts += 1
            phone_otp.save()
            remaining = 3 - phone_otp.attempts
            raise serializers.ValidationError({
                'otp': f'Invalid OTP. {remaining} attempts remaining.'
            })
        
        # Mark OTP as verified
        phone_otp.is_verified = True
        phone_otp.save()
        
        attrs['user'] = user
        return attrs
