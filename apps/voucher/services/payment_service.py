"""
Payment Service Layer.
Handles payment creation, allocation, and business logic.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.voucher.models import Payment, PaymentLine, Voucher, VoucherType
from apps.invoice.models import Invoice
from apps.party.models import Party
from apps.accounting.models import Ledger
from apps.company.models import Company, Sequence


class PaymentService:
    """Service for managing payments and receipts."""
    
    @staticmethod
    @transaction.atomic
    def create_payment(company, party_id, bank_account_id, payment_type, 
                      payment_date=None, payment_mode='CASH', reference_number='',
                      notes='', created_by=None):
        """
        Create a new payment or receipt.
        
        Args:
            company: Company instance
            party_id: Party UUID
            bank_account_id: Bank/Cash ledger UUID
            payment_type: 'PAYMENT' (outgoing) or 'RECEIPT' (incoming)
            payment_date: Payment date (defaults to today)
            payment_mode: Payment mode (CASH, CHEQUE, etc.)
            reference_number: Cheque/reference number
            notes: Additional notes
            created_by: User creating the payment
        
        Returns:
            Payment instance
        """
        # Validate party
        try:
            party = Party.objects.get(company=company, id=party_id)
        except Party.DoesNotExist:
            raise ValidationError(f"Party {party_id} not found")
        
        # Validate bank account (must be a ledger)
        try:
            bank_account = Ledger.objects.get(company=company, id=bank_account_id)
        except Ledger.DoesNotExist:
            raise ValidationError(f"Bank account {bank_account_id} not found")
        
        # Validate payment type
        if payment_type not in ['PAYMENT', 'RECEIPT']:
            raise ValidationError(f"Invalid payment_type: {payment_type}. Must be PAYMENT or RECEIPT")
        
        # Create voucher first
        voucher_type = VoucherType.objects.get(
            company=company,
            code=payment_type  # Assumes PAYMENT and RECEIPT voucher types exist
        )
        
        # Generate voucher number
        sequence = Sequence.objects.select_for_update().get(
            company=company,
            key=f'VOUCHER_{payment_type}'
        )
        voucher_number = f"{payment_type[:3]}-{sequence.next_value:05d}"
        sequence.next_value += 1
        sequence.save()
        
        # Create voucher
        voucher = Voucher.objects.create(
            company=company,
            voucher_type=voucher_type,
            voucher_number=voucher_number,
            date=payment_date or timezone.now().date(),
            status='DRAFT',
            created_by=created_by
        )
        
        # Create payment
        payment = Payment.objects.create(
            company=company,
            voucher=voucher,
            party=party,
            bank_account=bank_account,
            payment_date=payment_date or timezone.now().date(),
            payment_mode=payment_mode,
            reference_number=reference_number,
            status='DRAFT',
            notes=notes
        )
        
        return payment
    
    @staticmethod
    @transaction.atomic
    def allocate_payment(payment, invoice_id, amount_applied):
        """
        Allocate payment to an invoice.
        
        Args:
            payment: Payment instance
            invoice_id: Invoice UUID
            amount_applied: Decimal amount to apply
        
        Returns:
            PaymentLine instance
        """
        # Validate payment status
        if payment.status != 'DRAFT':
            raise ValidationError(f"Cannot allocate {payment.status} payment")
        
        # Validate invoice
        try:
            invoice = Invoice.objects.get(company=payment.company, id=invoice_id)
        except Invoice.DoesNotExist:
            raise ValidationError(f"Invoice {invoice_id} not found")
        
        # Validate amount
        amount_applied = Decimal(str(amount_applied))
        if amount_applied <= 0:
            raise ValidationError("Amount must be greater than zero")
        
        # Check if invoice has outstanding amount
        outstanding = invoice.total_value - invoice.amount_received
        if amount_applied > outstanding:
            raise ValidationError(
                f"Amount {amount_applied} exceeds invoice outstanding {outstanding}"
            )
        
        # Check if allocation already exists
        existing = PaymentLine.objects.filter(
            payment=payment,
            invoice=invoice
        ).first()
        
        if existing:
            # Update existing allocation
            existing.amount_applied += amount_applied
            existing.save()
            return existing
        
        # Create new allocation
        payment_line = PaymentLine.objects.create(
            payment=payment,
            invoice=invoice,
            amount_applied=amount_applied
        )
        
        return payment_line
    
    @staticmethod
    @transaction.atomic
    def remove_allocation(payment_line_id):
        """
        Remove a payment allocation.
        
        Args:
            payment_line_id: PaymentLine UUID
        """
        try:
            line = PaymentLine.objects.get(id=payment_line_id)
            
            if line.payment.status != 'DRAFT':
                raise ValidationError(f"Cannot modify {line.payment.status} payment")
            
            line.delete()
        except PaymentLine.DoesNotExist:
            raise ValidationError(f"Payment line {payment_line_id} not found")
    
    @staticmethod
    def get_total_allocated(payment):
        """
        Get total amount allocated from a payment.
        
        Args:
            payment: Payment instance
        
        Returns:
            Decimal total allocated
        """
        total = PaymentLine.objects.filter(payment=payment).aggregate(
            total=Sum('amount_applied')
        )['total'] or Decimal('0')
        
        return total
