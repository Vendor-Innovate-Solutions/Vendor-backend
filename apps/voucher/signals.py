"""
Signal handlers for voucher posting operations.

These signals provide hooks for cache invalidation and data consistency
when vouchers are posted. Currently provides structure for future implementation.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from apps.voucher.models import Voucher, PaymentLine


@receiver(post_save, sender=Voucher)
def handle_voucher_posted(sender, instance, created, **kwargs):
    """
    Handle voucher posting events.
    
    This signal is triggered after a Voucher is saved. When a voucher transitions
    to 'POSTED' status, we need to invalidate cached financial data.
    
    Future implementations:
    - Invalidate LedgerBalance cache for affected ledgers
    - Trigger materialized view refresh
    - Notify Redis cache to clear trial balance/reports
    - Queue background tasks for report regeneration
    - Send notifications to users watching affected ledgers
    
    Args:
        sender: The Voucher model class
        instance: The actual voucher instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    if instance.status == 'POSTED':
        # TODO: Implement cache invalidation logic
        # Example pseudo-code:
        # 1. Get all ledgers affected by this voucher
        # affected_ledgers = instance.lines.values_list('ledger_id', flat=True).distinct()
        # 
        # 2. Invalidate LedgerBalance cache
        # cache.delete_many([f'ledger_balance_{lid}' for lid in affected_ledgers])
        # 
        # 3. Invalidate company-wide financial reports
        # cache.delete(f'trial_balance_{instance.company_id}_{instance.financial_year_id}')
        # cache.delete(f'profit_loss_{instance.company_id}_{instance.financial_year_id}')
        # cache.delete(f'balance_sheet_{instance.company_id}_{instance.financial_year_id}')
        # 
        # 4. Queue background task if using Celery
        # from apps.reporting.tasks import recalculate_ledger_balances
        # recalculate_ledger_balances.delay(instance.company_id, instance.financial_year_id)
        pass


@receiver(post_save, sender=PaymentLine)
def update_invoice_status_after_payment(sender, instance, created, **kwargs):
    """
    Update invoice outstanding amount when payment is applied.
    
    This signal triggers invoice.refresh_outstanding() which:
    - Recalculates amount_received from all PaymentLines
    - Updates invoice status (PAID / PARTIALLY_PAID)
    
    Args:
        sender: The PaymentLine model class
        instance: The PaymentLine instance that was saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    if not created:
        # Only process on creation
        return
    
    # Get the invoice and refresh its outstanding
    invoice = instance.invoice
    
    if invoice:
        try:
            invoice.refresh_outstanding()
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error refreshing invoice outstanding: {e}")


@receiver(post_save, sender=Voucher)
def rebuild_invoice_outstanding_after_reversal(sender, instance, created, **kwargs):
    """
    Rebuild invoice outstanding after voucher reversal.
    
    When a voucher is reversed, any associated invoices need to recalculate
    their outstanding amounts to reflect the reversal of payments or adjustments.
    
    This ensures outstanding integrity even for mixed adjustment scenarios.
    
    Args:
        sender: The Voucher model class
        instance: The Voucher instance that was saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    # Only process when a voucher is marked as REVERSED (not on creation)
    if created or instance.status != 'REVERSED':
        return
    
    # Skip if no reversed_voucher reference
    if not instance.reversed_voucher_id:
        return
    
    try:
        # Import here to avoid circular dependency
        from apps.invoice.models import Invoice
        
        # Find all invoices linked to the original (reversed) voucher
        # This handles payment vouchers that were applied to invoices
        invoices = Invoice.objects.filter(voucher=instance)
        
        for invoice in invoices:
            try:
                invoice.refresh_outstanding()
            except Exception as e:
                # Log but don't fail - individual invoice refresh errors
                # should not break the entire reversal process
                print(f"Error refreshing outstanding for invoice {invoice.invoice_number}: {e}")
    
    except ImportError:
        # Invoice model may not exist in all deployments
        pass
    except Exception as e:
        # Log general error but don't fail the save
        print(f"Error in rebuild_invoice_outstanding_after_reversal: {e}")


@receiver(pre_delete, sender=Voucher)
def handle_voucher_deletion(sender, instance, **kwargs):
    """
    Handle voucher deletion events.
    
    Before a voucher is deleted, we need to ensure data consistency and
    invalidate any cached financial data that included this voucher.
    
    Future implementations:
    - Check if voucher can be safely deleted (no dependencies)
    - Invalidate affected cache entries
    - Log deletion for audit trail
    - Notify users of deletion if needed
    
    Args:
        sender: The Voucher model class
        instance: The actual voucher instance being deleted
        **kwargs: Additional keyword arguments
    """
    if instance.status == 'POSTED':
        # TODO: Implement deletion validation and cache invalidation
        # Example pseudo-code:
        # 1. Prevent deletion if financial year is closed
        # if instance.financial_year.is_closed:
        #     raise ValidationError("Cannot delete vouchers in closed financial year")
        # 
        # 2. Store affected ledgers before deletion
        # affected_ledgers = list(instance.lines.values_list('ledger_id', flat=True).distinct())
        # 
        # 3. Invalidate cache (same as posting)
        # cache.delete_many([f'ledger_balance_{lid}' for lid in affected_ledgers])
        pass


# Additional signal ideas for future implementation:

# @receiver(post_save, sender=VoucherLine)
# def handle_voucher_line_change(sender, instance, created, **kwargs):
#     """Handle individual line item changes."""
#     pass

# @receiver(post_save, sender=FinancialYear)
# def handle_financial_year_closed(sender, instance, created, **kwargs):
#     """Handle financial year closing operations."""
#     if not created and instance.is_closed:
#         # Freeze all ledger balances for this year
#         # Generate final reports
#         # Lock vouchers from editing
#         pass
