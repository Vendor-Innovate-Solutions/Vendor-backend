"""
Payment API views.
RESTful endpoints for payment and receipt management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum

from core.permissions.base import RolePermission
from apps.voucher.models import Payment, PaymentLine, Voucher
from apps.voucher.services.payment_service import PaymentService
from apps.accounting.services.payment_posting_service import PaymentPostingService
from apps.voucher.services.voucher_reversal_service import VoucherReversalService
from apps.voucher.selectors import get_voucher
from apps.voucher.guards import (
    guard_financial_year_open,
    guard_voucher_not_reversed,
    guard_voucher_posted
)
from apps.voucher.api.serializers import (
    PaymentSerializer, PaymentListSerializer,
    PaymentLineSerializer, CreatePaymentSerializer,
    AllocatePaymentSerializer
)


# ================================================================
# CREATE PAYMENT (draft)
# ================================================================
class PaymentCreateView(APIView):
    """
    Create a new payment or receipt.
    
    POST: Create draft payment/receipt
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request):
        """Create a new payment."""
        company = request.company
        serializer = CreatePaymentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payment = PaymentService.create_payment(
                company=company,
                party_id=serializer.validated_data['party_id'],
                bank_account_id=serializer.validated_data['bank_account_id'],
                payment_type=serializer.validated_data['payment_type'],
                payment_date=serializer.validated_data.get('payment_date'),
                payment_mode=serializer.validated_data.get('payment_mode', 'CASH'),
                reference_number=serializer.validated_data.get('reference_number', ''),
                notes=serializer.validated_data.get('notes', ''),
                created_by=request.user
            )
            
            response_serializer = PaymentSerializer(payment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to create payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# LIST PAYMENTS
# ================================================================
class PaymentListView(APIView):
    """
    List all payments for the company.
    
    GET: List payments with filters
    """
    
    def get(self, request):
        """List payments with optional filters."""
        company = request.company
        
        # Get all payments
        qs = Payment.objects.filter(company=company).select_related(
            'party', 'bank_account', 'voucher', 'voucher__voucher_type'
        ).prefetch_related('lines').order_by('-payment_date', '-created_at')
        
        # Apply filters
        payment_status = request.query_params.get('status')
        if payment_status:
            qs = qs.filter(status=payment_status)
        
        payment_type = request.query_params.get('payment_type')
        if payment_type:
            qs = qs.filter(voucher__voucher_type__code=payment_type)
        
        party_id = request.query_params.get('party')
        if party_id:
            qs = qs.filter(party_id=party_id)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(payment_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(payment_date__lte=end_date)
        
        serializer = PaymentListSerializer(qs, many=True)
        return Response(serializer.data)


# ================================================================
# GET PAYMENT DETAILS
# ================================================================
class PaymentDetailView(APIView):
    """
    Get payment details with allocations.
    
    GET: Get payment details
    """
    
    def get(self, request, payment_id):
        """Get payment details."""
        company = request.company
        
        try:
            payment = Payment.objects.select_related(
                'party', 'bank_account', 'voucher', 'voucher__voucher_type'
            ).prefetch_related('lines__invoice').get(
                company=company,
                id=payment_id
            )
            
            serializer = PaymentSerializer(payment)
            return Response(serializer.data)
            
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )


# ================================================================
# ALLOCATE TO INVOICE
# ================================================================
class PaymentAllocateView(APIView):
    """
    Allocate payment to an invoice.
    
    POST: Create payment allocation
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request, payment_id):
        """Allocate payment to invoice."""
        company = request.company
        serializer = AllocatePaymentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get payment
            payment = Payment.objects.get(company=company, id=payment_id)
            
            # Allocate
            line = PaymentService.allocate_payment(
                payment=payment,
                invoice_id=serializer.validated_data['invoice_id'],
                amount_applied=serializer.validated_data['amount_applied']
            )
            
            response_serializer = PaymentLineSerializer(line)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ================================================================
# REMOVE ALLOCATION
# ================================================================
class PaymentRemoveAllocationView(APIView):
    """
    Remove a payment allocation.
    
    DELETE: Remove allocation
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def delete(self, request, payment_id, line_id):
        """Remove payment allocation."""
        company = request.company
        
        try:
            # Verify payment belongs to company
            payment = Payment.objects.get(company=company, id=payment_id)
            
            # Remove allocation
            PaymentService.remove_allocation(line_id)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ================================================================
# POST PAYMENT (voucher + ledger entries)
# ================================================================
class PaymentPostVoucherView(APIView):
    """
    Post a payment to the accounting system.
    
    POST: Post payment (creates voucher entries, updates ledgers, applies to invoices)
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request, payment_id):
        """Post payment to accounting system."""
        company = request.company
        
        try:
            # Get payment
            payment = Payment.objects.get(company=company, id=payment_id)
            
            # Check payment status
            if payment.status == 'POSTED':
                return Response(
                    {
                        'error': 'Payment already posted',
                        'voucher_id': str(payment.voucher.id) if payment.voucher else None
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if payment.status == 'CANCELLED':
                return Response(
                    {'error': 'Cannot post cancelled payment'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if payment has allocations
            allocations = PaymentLine.objects.filter(payment=payment)
            if not allocations.exists():
                return Response(
                    {'error': 'Payment must have at least one allocation'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Post payment using posting service
            posted_voucher = PaymentPostingService.post_payment_voucher(
                voucher_id=payment.voucher.id,
                posted_by=request.user
            )
            
            # Update payment status
            payment.status = 'POSTED'
            payment.posted_voucher = posted_voucher
            payment.save(update_fields=['status', 'posted_voucher'])
            
            return Response({
                'voucher_id': str(posted_voucher.id),
                'voucher_number': posted_voucher.voucher_number,
                'status': 'POSTED',
                'message': 'Payment posted successfully'
            })
            
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to post payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# VOUCHER REVERSAL
# ================================================================
class VoucherReversalView(APIView):
    """
    Reverse a posted voucher.
    
    POST: Create reversal voucher (opposite entries)
    Requires: ADMIN or ACCOUNTANT role
    
    This creates a new voucher with opposite DR/CR entries, maintaining
    immutable audit trail. Original voucher is marked as REVERSED.
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request, voucher_id):
        """
        Reverse a voucher.
        
        Body params:
            reason (str): Reason for reversal (required)
            override (bool): Override financial year lock (default: False)
                            Only ADMIN with override=True can reverse closed FY
        """
        company = request.company
        reason = request.data.get('reason', '').strip()
        override = request.data.get('override', False)
        
        # Validate reason provided
        if not reason:
            return Response(
                {'error': 'Reason for reversal is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get voucher with company scoping
            voucher = get_voucher(company, voucher_id)
            
            # Guard: Check voucher is posted
            guard_voucher_posted(voucher)
            
            # Guard: Check not already reversed
            guard_voucher_not_reversed(voucher)
            
            # Guard: Check financial year is open (or override allowed)
            # Only ADMIN role can use override
            allow_override = override and 'ADMIN' in getattr(request.user, 'roles', [])
            guard_financial_year_open(voucher, allow_override=allow_override)
            
            # Perform reversal
            reversal_service = VoucherReversalService(user=request.user)
            reversal_voucher = reversal_service.reverse_voucher(
                voucher=voucher,
                reversal_reason=reason,
                reversal_date=None  # defaults to now
            )
            
            return Response({
                'reversed_voucher': str(reversal_voucher.id),
                'reversed_voucher_number': reversal_voucher.voucher_number,
                'original_voucher': str(voucher.id),
                'original_voucher_number': voucher.voucher_number,
                'status': 'REVERSED',
                'reason': reason,
                'message': f'Voucher {voucher.voucher_number} reversed successfully'
            }, status=status.HTTP_200_OK)
            
        except Voucher.DoesNotExist:
            return Response(
                {'error': 'Voucher not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to reverse voucher: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
