"""
GST Signals

Handles GST tracking and summary generation after voucher posting.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.voucher.models import Voucher


@receiver(post_save, sender=Voucher)
def on_voucher_posted_generate_gst(sender, instance, created, **kwargs):
    """
    Generate or update GST summary when a sales voucher is posted.
    
    Triggers on:
    - Voucher status change to "POSTED"
    - Voucher type: SALES
    
    Process:
    1. Check if voucher is POSTED and type is SALES
    2. Get related sales invoice
    3. Refresh invoice GST totals
    
    Note: This ensures GST summaries are accurate after posting.
    GST summaries are used for GSTR-1 and GSTR-3B generation.
    """
    # Only process when voucher is posted (not on creation)
    if created:
        return
    
    # Only process SALES vouchers that are POSTED
    if instance.status != "POSTED":
        return
    
    if instance.voucher_type.code != "SALES":
        return
    
    # Get related sales invoice
    try:
        # Check if this voucher has a sales invoice
        if hasattr(instance, 'salesinvoice'):
            invoice = instance.salesinvoice
            
            # Refresh GST totals
            # This will recalculate or ensure GST summary is up to date
            if hasattr(invoice, 'refresh_gst_summary'):
                invoice.refresh_gst_summary()
            
            # Log the GST tracking
            from apps.system.models import AuditLog
            AuditLog.objects.create(
                company=instance.company,
                user=instance.updated_by if hasattr(instance, 'updated_by') else None,
                action="GST_OUTPUT_TRACKED",
                entity_type="Invoice",
                entity_id=invoice.id,
                description=f"GST output tracked for sales invoice {invoice.invoice_number} after posting voucher {instance.voucher_number}"
            )
    except Exception as e:
        # Log error but don't fail the posting
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate GST summary for voucher {instance.id}: {str(e)}")


@receiver(post_save, sender=Voucher)
def on_purchase_gst_input(sender, instance, created, **kwargs):
    """
    Track input GST (ITC) when a purchase voucher is posted.
    
    Triggers on:
    - Voucher status change to "POSTED"
    - Voucher type: PURCHASE
    
    Process:
    1. Check if voucher is POSTED and type is PURCHASE
    2. Get related purchase invoice
    3. Track ITC for GSTR-3B calculation
    
    Note: This prepares input tax credit data for GST returns.
    Purchase GST can be offset against output GST in GSTR-3B.
    """
    # Only process when voucher is posted (not on creation)
    if created:
        return
    
    # Only process PURCHASE vouchers that are POSTED
    if instance.status != "POSTED":
        return
    
    if instance.voucher_type.code != "PURCHASE":
        return
    
    # Get related purchase invoice
    try:
        # Check if this voucher has a purchase invoice
        if hasattr(instance, 'purchaseinvoice'):
            invoice = instance.purchaseinvoice
            
            # Refresh GST totals for ITC tracking
            if hasattr(invoice, 'refresh_gst_summary'):
                invoice.refresh_gst_summary()
            
            # Log the ITC tracking
            from apps.system.models import AuditLog
            AuditLog.objects.create(
                company=instance.company,
                user=instance.updated_by if hasattr(instance, 'updated_by') else None,
                action="GST_INPUT_TRACKED",
                entity_type="Invoice",
                entity_id=invoice.id,
                description=f"GST input (ITC) tracked for purchase invoice {invoice.invoice_number} after posting voucher {instance.voucher_number}"
            )
    except Exception as e:
        # Log error but don't fail the posting
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to track ITC for voucher {instance.id}: {str(e)}")


# Note: GST summaries are stored in InvoiceGSTSummary model
# These signals ensure summaries are created/updated after posting
# This maintains separation between transaction recording (voucher posting)
# and compliance reporting (GST returns)
