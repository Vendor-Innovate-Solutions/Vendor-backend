"""
User registration and phone OTP verification APIs.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from apps.users.models import PhoneOTP
from apps.users.serializers import (
    UserRegistrationSerializer,
    SendPhoneOTPSerializer,
    VerifyPhoneOTPSerializer,
    UserDetailSerializer,
    UserLoginResponseSerializer,
    RoleSelectionSerializer,
    UserContextSerializer
)
from twilio.rest import Client

User = get_user_model()


class UserRegistrationView(APIView):
    """
    User registration endpoint.
    
    POST /users/register/
    {
        "email": "user@example.com",
        "phone": "+1234567890",
        "full_name": "John Doe",
        "password": "securepassword123"
    }
    
    Response:
    {
        "user": {
            "id": 1,
            "email": "user@example.com",
            "phone": "+1234567890",
            "full_name": "John Doe",
            "phone_verified": false,
            "created_at": "2026-01-27T08:50:00Z",
            "updated_at": "2026-01-27T08:50:00Z"
        },
        "access": "eyJ0eXAiOiJKV1QiLCJhb...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhb..."
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data.get('phone')
            
            # Check if phone number is verified
            phone_verified = PhoneOTP.objects.filter(
                phone_number=phone,
                is_verified=True,
                user__isnull=True  # Only pre-registration verifications
            ).exists()
            
            if not phone_verified:
                return Response(
                    {
                        "error": "Phone number must be verified before registration.",
                        "detail": "Please verify your phone number using the OTP sent to your phone."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create user with verified phone
            user = serializer.save()
            user.phone_verified = True
            user.save()
            
            # Link the verified phone OTP to the user
            PhoneOTP.objects.filter(
                phone_number=phone,
                is_verified=True,
                user__isnull=True
            ).update(user=user)
            
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                "user": UserDetailSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "Registration successful. Your phone number is verified."
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendPhoneOTPView(APIView):
    """
    Send OTP to phone number for verification.
    Supports both pre-registration verification and existing user verification.
    
    POST /users/send-phone-otp/
    {
        "phone": "+1234567890"
    }
    
    Response:
    {
        "message": "OTP sent successfully",
        "phone": "+1234567890",
        "expires_in_minutes": 10
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = SendPhoneOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            
            try:
                # Check if phone is already registered
                existing_user = User.objects.filter(phone=phone).first()
                if existing_user:
                    return Response(
                        {"error": "This phone number is already registered. Please login instead."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create OTP without user (for pre-registration verification)
                phone_otp = PhoneOTP.objects.create(
                    user=None,
                    phone_number=phone
                )
                
                # Send OTP via Twilio
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                message = client.messages.create(
                    body=f"Your Vendor OTP verification code is: {phone_otp.otp}. It will expire in 10 minutes.",
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=phone
                )
                
                return Response(
                    {
                        "message": "OTP sent successfully",
                        "phone": phone,
                        "expires_in_minutes": 10
                    },
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyPhoneOTPView(APIView):
    """
    Verify phone OTP and mark phone as verified.
    Supports both pre-registration verification and existing user verification.
    
    POST /users/verify-phone-otp/
    {
        "phone": "+1234567890",
        "otp": "123456"
    }
    
    Response:
    {
        "message": "Phone number verified successfully",
        "phone_verified": true,
        "phone": "+1234567890"
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyPhoneOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            otp = serializer.validated_data['otp']
            
            try:
                # Find the latest OTP
                phone_otp = PhoneOTP.objects.filter(
                    phone_number=phone,
                    is_verified=False
                ).latest('created_at')
                
                if phone_otp.is_expired():
                    return Response(
                        {"error": "OTP has expired. Please request a new one."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if phone_otp.attempts >= 3:
                    return Response(
                        {"error": "Maximum OTP attempts exceeded. Please request a new OTP."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if phone_otp.otp != otp:
                    phone_otp.attempts += 1
                    phone_otp.save()
                    return Response(
                        {"error": "Invalid OTP. Please try again."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Mark OTP as verified
                phone_otp.is_verified = True
                phone_otp.save()
                
                # If user exists (post-registration verification), mark phone as verified
                if phone_otp.user:
                    phone_otp.user.phone_verified = True
                    phone_otp.user.save()
                    return Response(
                        {
                            "message": "Phone number verified successfully",
                            "phone_verified": True,
                            "user": UserDetailSerializer(phone_otp.user).data
                        },
                        status=status.HTTP_200_OK
                    )
                
                # Pre-registration verification
                return Response(
                    {
                        "message": "Phone number verified successfully. You can now proceed with registration.",
                        "phone_verified": True,
                        "phone": phone
                    },
                    status=status.HTTP_200_OK
                )
            except PhoneOTP.DoesNotExist:
                return Response(
                    {"error": "No OTP found for this phone number. Please request a new one."},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    """
    Get authenticated user details.
    
    GET /users/me/
    
    Response:
    {
        "id": 1,
        "email": "user@example.com",
        "phone": "+1234567890",
        "full_name": "John Doe",
        "phone_verified": true,
        "created_at": "2026-01-27T08:50:00Z",
        "updated_at": "2026-01-27T08:50:00Z"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RoleSelectionView(APIView):
    """
    User role selection during onboarding.
    
    POST /auth/select-role
    {
        "role": "MANUFACTURER"
    }
    
    Response:
    {
        "message": "Role selected successfully",
        "role": "MANUFACTURER",
        "user": {...user details...}
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = RoleSelectionSerializer(data=request.data)
        
        if serializer.is_valid():
            request.user.selected_role = serializer.validated_data['role']
            request.user.is_internal_user = True  # Mark as internal user
            request.user.save()
            
            return Response(
                {
                    "message": "Role selected successfully",
                    "role": request.user.selected_role,
                    "user": UserDetailSerializer(request.user).data
                },
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserContextView(APIView):
    """
    Resolve user context after login.
    Returns user's role, companies, and default company.
    
    GET /me/context
    
    Response:
    {
        "user_id": "...",
        "email": "user@example.com",
        "full_name": "John Doe",
        "role": "MANUFACTURER",
        "role_selected": true,
        "has_company": true,
        "companies": [
            {
                "id": "company-uuid",
                "name": "ABC Manufacturing",
                "code": "ABC001",
                "role": "OWNER",
                "is_default": true
            }
        ],
        "default_company": {
            "id": "company-uuid",
            "name": "ABC Manufacturing",
            "code": "ABC001",
            "role": "OWNER"
        },
        "default_company_id": "company-uuid",
        "is_internal_user": true,
        "is_portal_user": false
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserContextSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
