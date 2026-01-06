"""
Invoice Generation Service
Generates invoices from sales orders with GST tax calculation.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.models import SalesOrder
from apps.invoice.models import Invoice, InvoiceLine
from apps.company.models import Sequence
from core.exceptions import AlreadyPosted


class InvoiceGenerationService:
    """
    Service for generating invoices from sales orders.
    
    Workflow:
    1. SalesOrder(CONFIRMED) → generate_from_sales_order() → Invoice(DRAFT)
    2. Posting engine creates voucher + StockMovement OUT
    3. mark_invoiced() updates SalesOrder to INVOICED status
    """

    # -------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def _next_number(company, key="invoice"):
        """
        Generate next invoice number using company sequence.
        
        Args:
            company: Company instance
            key: Sequence key (default: "invoice")
            
        Returns:
            Formatted invoice number (e.g., "INV-000001")
        """
        seq, created = Sequence.objects.select_for_update().get_or_create(
            company=company,
            key=key,
            defaults={
                'last_value': 0,
                'prefix': 'INV'
            }
        )
        
        # Increment and save
        seq.last_value += 1
        seq.save(update_fields=['last_value', 'updated_at'])
        
        # Format with padding
        return f"{seq.prefix}-{seq.last_value:06d}"

    # -------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def generate_from_sales_order(
        sales_order: SalesOrder,
        created_by,
        partial_allowed=False,
        apply_gst=True,
        invoice_date=None,
        due_date=None,
        company_state_code=None  # must be determined from Company.tax_registration
    ):
        """
        Generate DRAFT Invoice from CONFIRMED SalesOrder.
        
        Does NOT modify stock or ledger. Posting engine handles that.
        GST is applied here to store tax breakdowns before posting.
        
        Args:
            sales_order: SalesOrder instance (must be CONFIRMED or PARTIAL_INVOICED)
            created_by: User creating the invoice
            partial_allowed: Allow multiple invoices for same order
            apply_gst: Whether to apply GST tax calculation
            invoice_date: Invoice date (defaults to today)
            due_date: Payment due date (defaults to invoice_date)
            company_state_code: Company state code for GST calculation
            
        Returns:
            Invoice instance (DRAFT status)
            
        Raises:
            AlreadyPosted: If sales order already posted
            ValidationError: If sales order not ready for invoicing
        """

        # -------- VALIDATIONS --------
        if sales_order.status == "POSTED":
            raise AlreadyPosted("Sales order already posted")

        if sales_order.status not in ("CONFIRMED", "PARTIAL_INVOICED"):
            raise ValidationError(
                "Sales order must be CONFIRMED or PARTIAL_INVOICED before invoicing"
            )

        if not sales_order.items.exists():
            raise ValidationError("Cannot invoice empty sales order")

        existing = Invoice.objects.filter(
            company=sales_order.company, 
            sales_order=sales_order
        )
        if existing.exists() and not partial_allowed:
            raise ValidationError("Invoice already created for this sales order")

        # Financial year is resolved by posting engine when posting voucher
        fy = None

        invoice_number = InvoiceGenerationService._next_number(sales_order.company)
        invoice_date = invoice_date or timezone.now().date()
        due_date = due_date or invoice_date

        invoice = Invoice.objects.create(
            company=sales_order.company,
            invoice_number=invoice_number,
            invoice_type="SALES",
            party=sales_order.customer,
            currency=sales_order.currency,
            invoice_date=invoice_date,
            due_date=due_date,
            financial_year=fy,
            status="DRAFT",   # DRAFT until voucher is posted
            created_by=created_by,
            sales_order=sales_order
        )

        # -------- COPY LINES --------
        # No item-level tax stored here — tax service will create InvoiceGSTLine entries
        line_no = 1
        for line in sales_order.items.all():
            InvoiceLine.objects.create(
                invoice=invoice,
                line_no=line_no,
                item=line.item,
                description=line.item.name,
                quantity=line.quantity,
                unit_rate=line.unit_rate,
                uom=line.uom,
                line_total=line.quantity * line.unit_rate
            )
            line_no += 1

        # -------- APPLY GST BEFORE POSTING --------
        # company_state_code MUST be driven from company.tax registrations
        if apply_gst and company_state_code:
            try:
                from integrations.gst.services.apply_tax import apply_gst_to_invoice
                apply_gst_to_invoice(invoice, company_state_code)
            except ImportError:
                # GST service not yet implemented, skip
                pass

        # -------- UPDATE ORDER STATE --------
        # Do NOT finalize order until posting is done
        if partial_allowed:
            sales_order.status = "PARTIAL_INVOICED"
        else:
            sales_order.status = "INVOICE_CREATED_PENDING_POSTING"
        sales_order.save(update_fields=["status"])

        return invoice

    # -------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def mark_invoiced(sales_order: SalesOrder):
        """
        Mark sales order as INVOICED after posting engine completes.
        
        Called AFTER posting engine successfully posts voucher.
        
        Args:
            sales_order: SalesOrder instance
            
        Returns:
            Updated SalesOrder instance
            
        Raises:
            ValidationError: If sales order not in correct status
        """
        if sales_order.status not in ("INVOICE_CREATED_PENDING_POSTING", "PARTIAL_INVOICED"):
            raise ValidationError("Sales order not ready to mark invoiced")

        sales_order.status = "INVOICED"
        sales_order.invoiced_at = timezone.now()
        sales_order.save(update_fields=["status", "invoiced_at"])
        return sales_order
