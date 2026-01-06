"""
Selector pattern for Invoice app.

Selectors encapsulate all data retrieval logic with proper company scoping.
Never use Model.objects.get(id=...) directly - always use selectors.
"""
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet, Q
from apps.invoice.models import Invoice, InvoiceLine
from apps.company.models import Company


def get_invoice(company: Company, invoice_id: int) -> Invoice:
    """
    Retrieve a single invoice with company validation.
    
    Args:
        company: Company instance for scoping
        invoice_id: Invoice ID
    
    Returns:
        Invoice instance
    
    Raises:
        Http404: If invoice not found or belongs to different company
    """
    return get_object_or_404(
        Invoice.objects.select_related('party', 'currency', 'financial_year', 'sales_order', 'purchase_order'),
        company=company,
        id=invoice_id
    )


def list_invoices(company: Company, filters: dict = None) -> QuerySet:
    """
    List invoices for a company with optional filters.
    
    Args:
        company: Company instance for scoping
        filters: Optional dict of filter parameters
    
    Returns:
        QuerySet of invoices
    """
    qs = Invoice.objects.filter(company=company).select_related(
        'party', 'currency', 'financial_year', 'sales_order', 'purchase_order'
    ).prefetch_related('lines')
    
    if filters:
        # Apply filters (status, date range, customer, etc.)
        if 'status' in filters:
            qs = qs.filter(status=filters['status'])
        
        if 'customer_id' in filters:
            qs = qs.filter(customer_id=filters['customer_id'])
        
        if 'start_date' in filters:
            qs = qs.filter(invoice_date__gte=filters['start_date'])
        
        if 'end_date' in filters:
            qs = qs.filter(invoice_date__lte=filters['end_date'])
    
    return qs.order_by('-invoice_date', '-invoice_number')


def get_invoice_lines(company: Company, invoice_id: int) -> QuerySet:
    """
    Get all lines for an invoice with company validation.
    
    Args:
        company: Company instance for scoping
        invoice_id: Invoice ID
    
    Returns:
        QuerySet of invoice lines
    
    Raises:
        Http404: If invoice not found or belongs to different company
    """
    # First verify invoice belongs to company
    invoice = get_invoice(company, invoice_id)
    
    return InvoiceLine.objects.filter(invoice=invoice).select_related(
        'item', 'uom'
    ).order_by('line_no')


def get_pending_invoices(company: Company) -> QuerySet:
    """
    Get all pending (unpaid) invoices for a company.
    
    Args:
        company: Company instance for scoping
    
    Returns:
        QuerySet of pending invoices
    """
    return Invoice.objects.filter(
        company=company,
        status='PENDING'
    ).select_related('party', 'sales_order').order_by('invoice_date')


def list_outstanding_invoices(company: Company) -> QuerySet:
    """
    Get all outstanding (not fully paid) invoices.
    
    Outstanding = invoice not fully paid, where amount_received < total_value.
    
    Args:
        company: Company instance for scoping
    
    Returns:
        QuerySet of outstanding invoices
    """
    return (
        Invoice.objects
        .filter(company=company)
        .exclude(status="PAID")
        .select_related("party", "currency")
        .order_by("-invoice_date")
    )


def get_invoice_by_number(company: Company, invoice_number: str) -> Invoice:
    """
    Retrieve invoice by invoice number with company validation.
    
    Args:
        company: Company instance for scoping
        invoice_number: Invoice number (e.g., "INV-2024-0001")
    
    Returns:
        Invoice instance
    
    Raises:
        Http404: If invoice not found or belongs to different company
    """
    return get_object_or_404(
        Invoice.objects.select_related('party', 'sales_order', 'purchase_order'),
        company=company,
        invoice_number=invoice_number
    )
