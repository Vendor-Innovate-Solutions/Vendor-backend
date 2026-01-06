"""
Payment Posting Service
Posts payment/receipt vouchers and applies payments to invoices.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.voucher.models import Voucher, VoucherLine, Payment, PaymentLine
from core.posting_exceptions import validate_double_entry, AlreadyPosted
from apps.invoice.models import Invoice
from apps.accounting.models import Ledger, LedgerBalance
from apps.system.models import IntegrationEvent, AuditLog


class PaymentPostingService:
    """
    Service for posting payment and receipt vouchers.
    
    Handles:
    - Payment/Receipt voucher posting
    - Invoice settlement
    - Advance payment tracking
    - Ledger balance updates
    - Double-entry validation
    """

    @staticmethod
    @transaction.atomic
    def post_payment_voucher(voucher_id, posted_by, idempotency_key=None):
        """
        Posts a Payment or Receipt Voucher, then applies payments to invoices.
        
        Supports:
            - settlement of multiple invoices
            - overpayment tracking as advance
            - idempotency
            - ledger balance + invoice outstanding
            
        Args:
            voucher_id: Voucher ID to post
            posted_by: User posting the voucher
            idempotency_key: Optional key for idempotent posting
            
        Returns:
            Posted Voucher instance
            
        Raises:
            AlreadyPosted: If voucher already posted
            ValidationError: If validation fails
        """
        voucher = Voucher.objects.select_for_update().get(id=voucher_id)

        # --- idempotency ---
        if voucher.status == "POSTED":
            raise AlreadyPosted("Voucher already posted")

        payment = Payment.objects.select_for_update().get(voucher=voucher)
        lines = PaymentLine.objects.filter(payment=payment)

        if not lines.exists():
            raise ValidationError("Payment voucher contains no payment lines")

        vt = voucher.voucher_type
        if vt.category not in ("PAYMENT", "RECEIPT"):
            raise ValidationError("VoucherType must be PAYMENT or RECEIPT")

        # --- Determine mode semantics ---
        # PAYMENT   => money going OUT  => party DR, bank CR
        # RECEIPT   => money coming IN  => party CR, bank DR
        payment_mode = vt.category

        # --- Validate bank ledger exists ---
        bank_ledger = payment.bank_account if payment.bank_account else None
        if not bank_ledger:
            raise ValidationError("Payment voucher missing bank ledger")

        # --- Ledger Lines Build ---
        ledger_lines = []
        total_amount = Decimal("0")

        for pl in lines:
            if pl.invoice_id:
                invoice = Invoice.objects.select_for_update().get(id=pl.invoice_id)
                party_ledger = invoice.party.ledger
            else:
                # advance payments when no invoice attached
                if not payment.party:
                    raise ValidationError("Advance payment requires party set on Payment")
                party_ledger = payment.party.ledger
                invoice = None

            total_amount += pl.amount_applied

            if payment_mode == "PAYMENT":
                # paying vendor/customer
                ledger_lines.append({"ledger": party_ledger, "amount": pl.amount_applied, "entry_type": "DR"})
            else:
                # receiving money
                ledger_lines.append({"ledger": party_ledger, "amount": pl.amount_applied, "entry_type": "CR"})

        # --- Bank side ---
        if payment_mode == "PAYMENT":
            ledger_lines.append({"ledger": bank_ledger, "amount": total_amount, "entry_type": "CR"})
        else:
            ledger_lines.append({"ledger": bank_ledger, "amount": total_amount, "entry_type": "DR"})

        # --- Integrity: Double entry ---
        validate_double_entry(ledger_lines)

        # --- Write VoucherLines ---
        line_no = 1
        for l in ledger_lines:
            VoucherLine.objects.create(
                voucher=voucher,
                ledger=l["ledger"],
                amount=l["amount"],
                entry_type=l["entry_type"],
                line_no=line_no
            )
            line_no += 1

        # --- Apply payments to invoices ---
        for pl in lines:
            if not pl.invoice_id:
                continue  # advance payment — no invoice

            invoice = Invoice.objects.select_for_update().get(id=pl.invoice_id)

            outstanding = PaymentPostingService._invoice_outstanding(invoice)

            if pl.amount_applied > outstanding:
                raise ValidationError(f"Payment exceeds outstanding on invoice {invoice.invoice_number}")

            invoice.amount_received = (invoice.amount_received or Decimal("0")) + pl.amount_applied

            # rounding
            invoice.amount_received = invoice.amount_received.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # status update
            if invoice.amount_received >= invoice.total_value:
                invoice.status = "PAID"
            else:
                invoice.status = "PARTIALLY_PAID"

            invoice.save(update_fields=["amount_received", "status"])

        # --- Update LedgerBalance cache ---
        PaymentPostingService._update_ledger_cache(voucher, ledger_lines)

        # --- Update voucher/payment states ---
        voucher.status = "POSTED"
        voucher.posted_at = timezone.now()
        voucher.save(update_fields=["status", "posted_at"])

        payment.status = "POSTED"
        payment.posted_voucher = voucher
        payment.save(update_fields=["status", "posted_voucher"])

        # --- audit + event hooks ---
        AuditLog.objects.create(
            company=voucher.company,
            actor_user=posted_by,
            action_type="PAYMENT_POST",
            object_type="Voucher",
            object_id=str(voucher.id),
            changes={"status": "POSTED"},
            created_at=timezone.now()
        )

        IntegrationEvent.objects.create(
            company=voucher.company,
            event_type="payment.posted",
            payload={"voucher_id": str(voucher.id)},
            status="PENDING"
        )

        return voucher


    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    @staticmethod
    def _invoice_outstanding(invoice: Invoice) -> Decimal:
        """
        Calculate outstanding amount on invoice.
        
        Args:
            invoice: Invoice instance
            
        Returns:
            Outstanding amount (total - received)
        """
        total_received = invoice.amount_received or Decimal("0")
        return (invoice.total_value or Decimal("0")) - total_received


    @staticmethod
    def _update_ledger_cache(voucher, ledger_lines):
        """
        Updates LedgerBalance cache model after posting.
        Assumes atomic transaction and lock via SELECT FOR UPDATE.
        
        Args:
            voucher: Voucher instance
            ledger_lines: List of dicts with ledger, amount, entry_type
        """
        for l in ledger_lines:
            # update cache same way posting engine would
            bal, _ = LedgerBalance.objects.select_for_update().get_or_create(
                company=voucher.company,
                ledger=l["ledger"],
                financial_year=voucher.financial_year
            )

            if l["entry_type"] == "DR":
                bal.balance_dr = (bal.balance_dr or Decimal("0")) + l["amount"]
            else:
                bal.balance_cr = (bal.balance_cr or Decimal("0")) + l["amount"]

            bal.last_posted_voucher = voucher
            bal.save(update_fields=["balance_dr", "balance_cr", "last_posted_voucher", "updated_at"])
