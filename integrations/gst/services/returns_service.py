"""
GST Return Generation Service

Handles generation of GSTR-1 and GSTR-3B returns from posted invoices.
"""
from decimal import Decimal
from django.db.models import Sum, Q
from django.db import transaction


class GSTReturnService:
    """
    Service for generating GST returns (GSTR-1, GSTR-3B).
    
    Processes posted invoices to generate compliance-ready GST return summaries
    per tax period (monthly).
    """
    
    @staticmethod
    def generate_gstr1(company, period: str):
        """
        Generate GSTR-1 (outward supplies) for a given period.
        
        Args:
            company: Company instance
            period: Tax period in YYYY-MM format (e.g., "2024-07")
            
        Returns:
            GSTR1 instance with aggregated outward supplies
            
        Process:
        1. Filter posted sales invoices for the period
        2. Aggregate taxable value, CGST, SGST, IGST
        3. Create GSTR1 record
        
        Note: Only invoices with status="POSTED" are included to ensure
        GST is only reported after accounting confirmation.
        """
        from apps.invoice.models import Invoice
        from integrations.gst.models import GSTR1, InvoiceGSTSummary
        
        # Parse period to year and month
        year, month = period.split('-')
        
        # Filter posted invoices for the period
        # Using invoice_date for period matching
        invoices_qs = Invoice.objects.filter(
            company=company,
            status="POSTED",
            invoice_type="SALES",
            invoice_date__year=year,
            invoice_date__month=month
        )
        
        # Get GST summaries for these invoices
        summaries_qs = InvoiceGSTSummary.objects.filter(
            invoice__in=invoices_qs
        )
        
        # Aggregate GST amounts
        agg = summaries_qs.aggregate(
            taxable=Sum("taxable_value"),
            cgst=Sum("cgst"),
            sgst=Sum("sgst"),
            igst=Sum("igst")
        )
        
        # Create GSTR1 record
        with transaction.atomic():
            gstr1, created = GSTR1.objects.update_or_create(
                company=company,
                period=period,
                defaults={
                    'outward_taxable': agg.get("taxable") or Decimal("0"),
                    'cgst': agg.get("cgst") or Decimal("0"),
                    'sgst': agg.get("sgst") or Decimal("0"),
                    'igst': agg.get("igst") or Decimal("0"),
                    'total_tax': (
                        (agg.get("cgst") or Decimal("0")) +
                        (agg.get("sgst") or Decimal("0")) +
                        (agg.get("igst") or Decimal("0"))
                    )
                }
            )
        
        return gstr1
    
    @staticmethod
    def generate_gstr3b(company, period: str):
        """
        Generate GSTR-3B (monthly return) for a given period.
        
        Args:
            company: Company instance
            period: Tax period in YYYY-MM format (e.g., "2024-07")
            
        Returns:
            GSTR3B instance with net tax liability
            
        Process:
        1. Get GSTR-1 data (outward supplies)
        2. Calculate inward ITC from purchase invoices (future)
        3. Compute net tax payable (output - input)
        4. Create GSTR-3B record
        
        Note: Input ITC from purchase invoices will be implemented
        once purchase voucher flow is complete.
        """
        from integrations.gst.models import GSTR1, GSTR3B, InvoiceGSTSummary
        from apps.invoice.models import Invoice
        
        # Get or generate GSTR-1 first
        try:
            gstr1 = GSTR1.objects.get(company=company, period=period)
        except GSTR1.DoesNotExist:
            gstr1 = GSTReturnService.generate_gstr1(company, period)
        
        # Calculate inward ITC from purchase invoices
        # Filter posted purchase invoices for the period
        year, month = period.split('-')
        
        purchase_invoices_qs = Invoice.objects.filter(
            company=company,
            status="POSTED",
            invoice_type="PURCHASE",
            invoice_date__year=year,
            invoice_date__month=month
        )
        
        # Get GST summaries for purchase invoices
        purchase_summaries_qs = InvoiceGSTSummary.objects.filter(
            invoice__in=purchase_invoices_qs
        )
        
        # Aggregate input ITC
        itc_agg = purchase_summaries_qs.aggregate(
            cgst=Sum("cgst"),
            sgst=Sum("sgst"),
            igst=Sum("igst")
        )
        
        inward_cgst_itc = itc_agg.get("cgst") or Decimal("0")
        inward_sgst_itc = itc_agg.get("sgst") or Decimal("0")
        inward_igst_itc = itc_agg.get("igst") or Decimal("0")
        
        # Calculate net tax payable
        cgst_payable = gstr1.cgst - inward_cgst_itc
        sgst_payable = gstr1.sgst - inward_sgst_itc
        igst_payable = gstr1.igst - inward_igst_itc
        
        # Create GSTR-3B record
        with transaction.atomic():
            gstr3b, created = GSTR3B.objects.update_or_create(
                company=company,
                period=period,
                defaults={
                    'outward_taxable': gstr1.outward_taxable,
                    'inward_itc_cgst': inward_cgst_itc,
                    'inward_itc_sgst': inward_sgst_itc,
                    'inward_itc_igst': inward_igst_itc,
                    'cgst_payable': max(cgst_payable, Decimal("0")),
                    'sgst_payable': max(sgst_payable, Decimal("0")),
                    'igst_payable': max(igst_payable, Decimal("0")),
                    'total_payable': (
                        max(cgst_payable, Decimal("0")) +
                        max(sgst_payable, Decimal("0")) +
                        max(igst_payable, Decimal("0"))
                    )
                }
            )
        
        return gstr3b
    
    @staticmethod
    def get_period_returns(company, period: str):
        """
        Get both GSTR-1 and GSTR-3B for a given period.
        
        Args:
            company: Company instance
            period: Tax period in YYYY-MM format
            
        Returns:
            dict with 'gstr1' and 'gstr3b' data
        """
        from integrations.gst.models import GSTR1, GSTR3B
        
        result = {
            'period': period,
            'company': company.name,
            'gstr1': None,
            'gstr3b': None
        }
        
        try:
            gstr1 = GSTR1.objects.get(company=company, period=period)
            result['gstr1'] = {
                'id': str(gstr1.id),
                'outward_taxable': str(gstr1.outward_taxable),
                'cgst': str(gstr1.cgst),
                'sgst': str(gstr1.sgst),
                'igst': str(gstr1.igst),
                'total_tax': str(gstr1.total_tax),
                'created_at': gstr1.created_at.isoformat(),
                'updated_at': gstr1.updated_at.isoformat(),
            }
        except GSTR1.DoesNotExist:
            pass
        
        try:
            gstr3b = GSTR3B.objects.get(company=company, period=period)
            result['gstr3b'] = {
                'id': str(gstr3b.id),
                'outward_taxable': str(gstr3b.outward_taxable),
                'inward_itc_cgst': str(gstr3b.inward_itc_cgst),
                'inward_itc_sgst': str(gstr3b.inward_itc_sgst),
                'inward_itc_igst': str(gstr3b.inward_itc_igst),
                'cgst_payable': str(gstr3b.cgst_payable),
                'sgst_payable': str(gstr3b.sgst_payable),
                'igst_payable': str(gstr3b.igst_payable),
                'total_payable': str(gstr3b.total_payable),
                'created_at': gstr3b.created_at.isoformat(),
                'updated_at': gstr3b.updated_at.isoformat(),
            }
        except GSTR3B.DoesNotExist:
            pass
        
        return result
