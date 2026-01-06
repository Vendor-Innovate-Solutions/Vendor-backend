"""
GST Models

Models for GST compliance and return generation.

NOTE: These models need to be created based on your gst_engine.txt specification.
The service layer and APIs are ready - just need the Django models.

Required Models:
1. GSTR1 - Outward supplies summary
2. GSTR3B - Monthly return with ITC
3. InvoiceGSTSummary - Per-invoice GST breakdown
4. GSTLedgerMapping - Map tax types to ledgers
5. InvoiceGSTLine - Per-line GST breakdown (optional)

Refer to gst_engine.txt for full model definitions.
"""

from django.db import models
from core.models import BaseModel, CompanyScopedModel
from decimal import Decimal


# TODO: Create these models based on gst_engine.txt
# For now, these are placeholder classes to prevent import errors

class GSTR1(CompanyScopedModel):
    """
    GSTR-1: Outward supplies summary (sales).
    
    TODO: Add full model definition from gst_engine.txt
    Expected fields:
    - period (CharField): YYYY-MM format
    - outward_taxable (DecimalField): Total taxable value
    - cgst (DecimalField): Total CGST
    - sgst (DecimalField): Total SGST
    - igst (DecimalField): Total IGST
    - total_tax (DecimalField): Sum of all taxes
    """
    period = models.CharField(max_length=7, help_text="YYYY-MM format")
    outward_taxable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    cgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    sgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    igst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    total_tax = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    
    class Meta:
        unique_together = ('company', 'period')
        verbose_name = 'GSTR-1'
        verbose_name_plural = 'GSTR-1 Returns'
        indexes = [
            models.Index(fields=['company', 'period']),
        ]
    
    def __str__(self):
        return f"GSTR-1 {self.period} - {self.company.name}"


class GSTR3B(CompanyScopedModel):
    """
    GSTR-3B: Monthly return with input tax credit.
    
    TODO: Add full model definition from gst_engine.txt
    Expected fields:
    - period (CharField): YYYY-MM format
    - outward_taxable (DecimalField): Total outward taxable
    - inward_itc_cgst (DecimalField): Input CGST credit
    - inward_itc_sgst (DecimalField): Input SGST credit
    - inward_itc_igst (DecimalField): Input IGST credit
    - cgst_payable (DecimalField): Net CGST payable
    - sgst_payable (DecimalField): Net SGST payable
    - igst_payable (DecimalField): Net IGST payable
    - total_payable (DecimalField): Total tax payable
    """
    period = models.CharField(max_length=7, help_text="YYYY-MM format")
    outward_taxable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    inward_itc_cgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    inward_itc_sgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    inward_itc_igst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    cgst_payable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    sgst_payable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    igst_payable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    total_payable = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    
    class Meta:
        unique_together = ('company', 'period')
        verbose_name = 'GSTR-3B'
        verbose_name_plural = 'GSTR-3B Returns'
        indexes = [
            models.Index(fields=['company', 'period']),
        ]
    
    def __str__(self):
        return f"GSTR-3B {self.period} - {self.company.name}"


class InvoiceGSTSummary(BaseModel):
    """
    Per-invoice GST summary.
    
    TODO: Add full model definition from gst_engine.txt
    Stores aggregated GST for each invoice.
    """
    invoice = models.OneToOneField(
        'invoice.Invoice',
        on_delete=models.CASCADE,
        related_name='gst_summary'
    )
    taxable_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    cgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    sgst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    igst = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    total_tax = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    total_value = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0'))
    
    class Meta:
        verbose_name = 'Invoice GST Summary'
        verbose_name_plural = 'Invoice GST Summaries'
    
    def __str__(self):
        return f"GST Summary - {self.invoice.invoice_number}"


class GSTLedgerMapping(CompanyScopedModel):
    """
    Maps GST tax types to accounting ledgers.
    
    TODO: Add full model definition from gst_engine.txt
    """
    tax_type = models.CharField(
        max_length=20,
        choices=[
            ('CGST', 'CGST Output'),
            ('SGST', 'SGST Output'),
            ('IGST', 'IGST Output'),
            ('CGST_INPUT', 'CGST Input'),
            ('SGST_INPUT', 'SGST Input'),
            ('IGST_INPUT', 'IGST Input'),
        ]
    )
    ledger = models.ForeignKey(
        'accounting.Ledger',
        on_delete=models.PROTECT,
        related_name='gst_mappings'
    )
    
    class Meta:
        unique_together = ('company', 'tax_type')
        verbose_name = 'GST Ledger Mapping'
        verbose_name_plural = 'GST Ledger Mappings'
    
    def __str__(self):
        return f"{self.tax_type} → {self.ledger.name}"


# Note: After creating proper models, remember to:
# 1. python manage.py makemigrations gst
# 2. python manage.py migrate
