"""
Security API endpoints for key exchange and secure operations.

This module provides APIs for:
1. Key Exchange - Establishing secure communication channels
2. Secure Data Transfer - Encrypting sensitive data for recipients

Use Cases:
- Secure document sharing between users
- Encrypted payment information exchange
- Secure API key distribution
- End-to-end encrypted messaging
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.core.cache import cache
import logging
import uuid
from datetime import timedelta

logger = logging.getLogger(__name__)


class KeyExchangeInitiateView(APIView):
    """
    Step 1 of Key Exchange: Generate RSA key pair for the session.
    
    POST /api/security/key-exchange/initiate/
    
    Response:
    {
        "session_id": "uuid",
        "public_key": "-----BEGIN PUBLIC KEY-----...",
        "expires_in_seconds": 300,
        "algorithm": "RSA-2048"
    }
    
    The client uses this public key to encrypt the session key.
    The session_id must be provided in the complete step.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Initiate key exchange by generating a new RSA key pair."""
        from core.security import KeyExchange
        
        try:
            exchange = KeyExchange()
            
            # Generate recipient (server) keys
            key_pair = exchange.generate_recipient_keys(key_size=2048)
            
            # Create a session ID
            session_id = str(uuid.uuid4())
            
            # Store private key in cache (expires in 5 minutes)
            cache_key = f"key_exchange:{request.user.id}:{session_id}"
            cache.set(cache_key, {
                'private_key_pem': key_pair.get_private_pem(),
                'user_id': str(request.user.id),
            }, timeout=300)  # 5 minutes
            
            logger.info(f"Key exchange initiated for user {request.user.id}, session {session_id}")
            
            return Response({
                'session_id': session_id,
                'public_key': key_pair.get_public_pem(),
                'expires_in_seconds': 300,
                'algorithm': 'RSA-2048',
                'usage': 'Use this public key to encrypt your session key, then send it to /key-exchange/complete/'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Key exchange initiation failed: {str(e)}")
            return Response(
                {'error': 'Failed to initiate key exchange'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KeyExchangeCompleteView(APIView):
    """
    Step 2 of Key Exchange: Receive encrypted session key from client.
    
    POST /api/security/key-exchange/complete/
    {
        "session_id": "uuid from initiate step",
        "encrypted_session_key": "base64 encoded encrypted key"
    }
    
    Response:
    {
        "success": true,
        "session_id": "uuid",
        "message": "Session key received. Use /secure-data/ endpoints for encrypted communication."
    }
    
    After this, both client and server share the session key for AES encryption.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Complete key exchange by receiving encrypted session key."""
        from core.security import KeyExchange, RSACipher
        import base64
        
        session_id = request.data.get('session_id')
        encrypted_key_b64 = request.data.get('encrypted_session_key')
        
        if not session_id or not encrypted_key_b64:
            return Response(
                {'error': 'session_id and encrypted_session_key are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Retrieve private key from cache
            cache_key = f"key_exchange:{request.user.id}:{session_id}"
            session_data = cache.get(cache_key)
            
            if not session_data:
                return Response(
                    {'error': 'Session expired or invalid. Please initiate key exchange again.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify user
            if session_data['user_id'] != str(request.user.id):
                return Response(
                    {'error': 'Invalid session'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Decrypt the session key
            exchange = KeyExchange()
            encrypted_key = base64.b64decode(encrypted_key_b64)
            
            # Load private key
            rsa_cipher = RSACipher()
            private_key = rsa_cipher.load_private_key_from_pem(
                session_data['private_key_pem'].encode()
            )
            
            # Recover session key
            session_key = exchange.recover_session_key(encrypted_key, private_key)
            
            # Store session key for subsequent encrypted communications
            session_cache_key = f"session_key:{request.user.id}:{session_id}"
            cache.set(session_cache_key, {
                'session_key': base64.b64encode(session_key).decode(),
                'user_id': str(request.user.id),
            }, timeout=3600)  # 1 hour
            
            # Remove the private key from cache (no longer needed)
            cache.delete(cache_key)
            
            logger.info(f"Key exchange completed for user {request.user.id}, session {session_id}")
            
            return Response({
                'success': True,
                'session_id': session_id,
                'message': 'Session key received. Use /secure-data/ endpoints for encrypted communication.',
                'expires_in_seconds': 3600
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Key exchange completion failed: {str(e)}")
            return Response(
                {'error': 'Failed to complete key exchange. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class SecureDataSendView(APIView):
    """
    Send encrypted data using the established session key.
    
    POST /api/security/secure-data/send/
    {
        "session_id": "uuid",
        "encrypted_data": "base64 encoded AES encrypted data",
        "recipient_id": "user_id of recipient (optional)"
    }
    
    Response:
    {
        "success": true,
        "message_id": "uuid",
        "message": "Data securely received and stored"
    }
    
    This endpoint receives AES-encrypted data from the client,
    decrypts it using the session key, and processes it securely.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Receive and decrypt secure data."""
        from core.security import AESCipher
        import base64
        
        session_id = request.data.get('session_id')
        encrypted_data_b64 = request.data.get('encrypted_data')
        
        if not session_id or not encrypted_data_b64:
            return Response(
                {'error': 'session_id and encrypted_data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Retrieve session key
            session_cache_key = f"session_key:{request.user.id}:{session_id}"
            session_data = cache.get(session_cache_key)
            
            if not session_data:
                return Response(
                    {'error': 'Session expired. Please establish a new key exchange.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Decrypt data
            cipher = AESCipher()
            session_key = base64.b64decode(session_data['session_key'])
            encrypted_data = base64.b64decode(encrypted_data_b64)
            
            decrypted_data = cipher.decrypt(encrypted_data, session_key)
            
            # Process the decrypted data (store, forward, etc.)
            message_id = str(uuid.uuid4())
            
            # Here you would typically:
            # 1. Store the data securely
            # 2. Forward to recipient if specified
            # 3. Trigger any business logic
            
            logger.info(f"Secure data received from user {request.user.id}, message {message_id}")
            
            return Response({
                'success': True,
                'message_id': message_id,
                'message': 'Data securely received',
                'data_size': len(decrypted_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Secure data receive failed: {str(e)}")
            return Response(
                {'error': 'Failed to process encrypted data'},
                status=status.HTTP_400_BAD_REQUEST
            )


class SecureDataReceiveView(APIView):
    """
    Receive encrypted data prepared for the current user.
    
    GET /api/security/secure-data/receive/
    Query params:
        - session_id: The active session ID
    
    Response:
    {
        "messages": [
            {
                "message_id": "uuid",
                "encrypted_data": "base64 encoded AES encrypted data",
                "from_user": "sender_id",
                "created_at": "timestamp"
            }
        ]
    }
    
    The client uses the session key to decrypt the data.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get encrypted messages for the user."""
        session_id = request.query_params.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify session exists
        session_cache_key = f"session_key:{request.user.id}:{session_id}"
        if not cache.get(session_cache_key):
            return Response(
                {'error': 'Session expired. Please establish a new key exchange.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # In a real implementation, fetch encrypted messages from database
        # For now, return empty list as placeholder
        return Response({
            'messages': [],
            'session_id': session_id,
            'message': 'No pending encrypted messages'
        }, status=status.HTTP_200_OK)


class SecurePaymentDataView(APIView):
    """
    Exchange sensitive payment information securely.
    
    This is a specialized endpoint for payment-related data that requires
    end-to-end encryption. Uses the established session key.
    
    POST /api/security/secure-payment/
    {
        "session_id": "uuid",
        "encrypted_payment_data": "base64 encoded encrypted payment info"
    }
    
    The payment data is:
    1. Decrypted using session key
    2. Validated
    3. Processed securely
    4. Response encrypted and returned
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Process encrypted payment data."""
        from core.security import AESCipher
        import base64
        import json
        
        session_id = request.data.get('session_id')
        encrypted_payment_b64 = request.data.get('encrypted_payment_data')
        
        if not session_id or not encrypted_payment_b64:
            return Response(
                {'error': 'session_id and encrypted_payment_data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Retrieve session key
            session_cache_key = f"session_key:{request.user.id}:{session_id}"
            session_data = cache.get(session_cache_key)
            
            if not session_data:
                return Response(
                    {'error': 'Session expired. Please establish a new key exchange.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Decrypt payment data
            cipher = AESCipher()
            session_key = base64.b64decode(session_data['session_key'])
            encrypted_data = base64.b64decode(encrypted_payment_b64)
            
            decrypted_data = cipher.decrypt(encrypted_data, session_key)
            
            # Parse and validate payment data
            try:
                payment_info = json.loads(decrypted_data.decode('utf-8'))
            except json.JSONDecodeError:
                return Response(
                    {'error': 'Invalid payment data format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required fields
            required_fields = ['amount', 'currency']
            for field in required_fields:
                if field not in payment_info:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Process payment (placeholder - integrate with payment gateway)
            transaction_id = str(uuid.uuid4())
            
            # Create encrypted response
            response_data = json.dumps({
                'transaction_id': transaction_id,
                'status': 'pending',
                'amount': payment_info['amount'],
                'currency': payment_info['currency']
            }).encode()
            
            encrypted_response = cipher.encrypt(response_data, session_key)
            
            logger.info(f"Secure payment processed for user {request.user.id}, tx {transaction_id}")
            
            return Response({
                'success': True,
                'transaction_id': transaction_id,
                'encrypted_response': base64.b64encode(encrypted_response).decode(),
                'message': 'Payment data received securely'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Secure payment processing failed: {str(e)}")
            return Response(
                {'error': 'Failed to process payment data'},
                status=status.HTTP_400_BAD_REQUEST
            )
