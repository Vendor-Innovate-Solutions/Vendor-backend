"""
Workflow Models

Implements maker-checker-poster approval pattern for financial transactions.
"""
from django.db import models
from django.contrib.auth import get_user_model
from core.models import BaseModel, CompanyScopedModel

User = get_user_model()


class ApprovalStatus(models.TextChoices):
    """Approval status enum."""
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class Approval(CompanyScopedModel):
    """
    Generic approval model for maker-checker workflow.
    
    Workflow States:
    DRAFT → APPROVAL_PENDING → APPROVED → POSTED
    
    Roles:
    - Maker: Creates and submits for approval
    - Checker: Approves or rejects
    - Poster: Posts approved transactions
    - Auditor: View-only access
    
    Usage:
    1. Maker creates voucher/order (DRAFT status)
    2. Maker submits for approval (creates Approval record with PENDING)
    3. Checker reviews and approves/rejects
    4. Poster can only post APPROVED transactions
    
    Example:
        # Submit for approval
        approval = Approval.objects.create(
            company=company,
            target_type='voucher',
            target_id=voucher.id,
            requested_by=maker_user,
            status='PENDING'
        )
        
        # Approve
        approval.approved_by = checker_user
        approval.status = 'APPROVED'
        approval.remarks = "All documents verified"
        approval.save()
    """
    target_type = models.CharField(
        max_length=50,
        help_text="Type of object (voucher, order, invoice, etc.)"
    )
    target_id = models.UUIDField(
        help_text="ID of the object requiring approval"
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approval_requests',
        help_text="User who requested approval (Maker)"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='approvals_given',
        null=True,
        blank=True,
        help_text="User who approved/rejected (Checker)"
    )
    status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING
    )
    remarks = models.TextField(
        blank=True,
        help_text="Approval/rejection remarks"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of approval/rejection"
    )
    
    class Meta:
        verbose_name = 'Approval'
        verbose_name_plural = 'Approvals'
        indexes = [
            models.Index(fields=['company', 'target_type', 'target_id']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['requested_by']),
            models.Index(fields=['approved_by']),
        ]
        # Ensure only one pending approval per target
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'target_type', 'target_id'],
                condition=models.Q(status='PENDING'),
                name='one_pending_approval_per_target'
            )
        ]
    
    def __str__(self):
        return f"{self.target_type} {self.target_id} - {self.status}"
    
    def approve(self, user: User, remarks: str = ""):
        """
        Approve the request.
        
        Args:
            user: User approving
            remarks: Approval remarks
        """
        from django.utils import timezone
        
        if self.status != ApprovalStatus.PENDING:
            from django.core.exceptions import ValidationError
            raise ValidationError("Can only approve pending approvals")
        
        self.status = ApprovalStatus.APPROVED
        self.approved_by = user
        self.remarks = remarks
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'remarks', 'approved_at', 'updated_at'])
    
    def reject(self, user: User, remarks: str):
        """
        Reject the request.
        
        Args:
            user: User rejecting
            remarks: Rejection reason (required)
        """
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        
        if not remarks:
            raise ValidationError("Rejection reason is required")
        
        if self.status != ApprovalStatus.PENDING:
            raise ValidationError("Can only reject pending approvals")
        
        self.status = ApprovalStatus.REJECTED
        self.approved_by = user
        self.remarks = remarks
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'remarks', 'approved_at', 'updated_at'])


class ApprovalRule(CompanyScopedModel):
    """
    Approval rules configuration per company.
    
    Defines which transactions require approval and approval thresholds.
    
    Example:
        # Vouchers > ₹10,000 require approval
        rule = ApprovalRule.objects.create(
            company=company,
            target_type='voucher',
            approval_required=True,
            threshold_amount=10000
        )
    """
    target_type = models.CharField(
        max_length=50,
        help_text="Type of object (voucher, order, invoice)"
    )
    approval_required = models.BooleanField(
        default=True,
        help_text="Whether approval is mandatory"
    )
    threshold_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Approval required if amount exceeds this"
    )
    auto_approve_below_threshold = models.BooleanField(
        default=False,
        help_text="Auto-approve if below threshold"
    )
    
    class Meta:
        unique_together = ('company', 'target_type')
        verbose_name = 'Approval Rule'
        verbose_name_plural = 'Approval Rules'
    
    def __str__(self):
        return f"{self.target_type} - Approval Required: {self.approval_required}"
