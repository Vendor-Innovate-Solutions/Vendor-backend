"""
Tally Prime Data Import Models
Tracks import jobs, field mappings, and import history
"""
from django.db import models
from django.conf import settings
from core.models import BaseModel, CompanyScopedModel
import uuid


class ImportStatus(models.TextChoices):
    """Status of import job"""
    PENDING = 'PENDING', 'Pending'
    VALIDATING = 'VALIDATING', 'Validating'
    VALIDATED = 'VALIDATED', 'Validated'
    IMPORTING = 'IMPORTING', 'Importing'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    PARTIAL = 'PARTIAL', 'Partially Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class DataType(models.TextChoices):
    """Types of data that can be imported"""
    LEDGER_GROUP = 'LEDGER_GROUP', 'Ledger Groups (Account Groups)'
    LEDGER = 'LEDGER', 'Ledgers'
    STOCK_GROUP = 'STOCK_GROUP', 'Stock Groups'
    STOCK_ITEM = 'STOCK_ITEM', 'Stock Items'
    STOCK_CATEGORY = 'STOCK_CATEGORY', 'Stock Categories'
    UNIT = 'UNIT', 'Units of Measure'
    GODOWN = 'GODOWN', 'Godowns (Warehouses)'
    PARTY = 'PARTY', 'Parties (Customers/Suppliers)'
    VOUCHER = 'VOUCHER', 'Vouchers'
    COST_CENTER = 'COST_CENTER', 'Cost Centers'
    COST_CATEGORY = 'COST_CATEGORY', 'Cost Categories'
    CURRENCY = 'CURRENCY', 'Currencies'
    OPENING_BALANCE = 'OPENING_BALANCE', 'Opening Balances'


class TallyImportJob(CompanyScopedModel):
    """
    Tracks a Tally import job
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # File information
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)
    
    # Import configuration
    data_types = models.JSONField(
        default=list,
        help_text="List of data types to import from this file"
    )
    
    # Source info
    tally_company_name = models.CharField(max_length=255, blank=True)
    tally_version = models.CharField(max_length=50, blank=True)
    export_date = models.DateField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING
    )
    
    # Progress tracking
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    skipped_records = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # User who initiated
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tally_imports'
    )
    
    # Error information
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Import options
    options = models.JSONField(
        default=dict,
        help_text="Import options like overwrite, skip_duplicates, etc."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tally Import Job"
        verbose_name_plural = "Tally Import Jobs"

    def __str__(self):
        return f"Import {self.id} - {self.original_filename} ({self.status})"
    
    @property
    def progress_percentage(self):
        if self.total_records == 0:
            return 0
        return round((self.processed_records / self.total_records) * 100, 2)


class TallyFieldMapping(CompanyScopedModel):
    """
    Custom field mappings for Tally to system conversion
    Allows users to customize how Tally fields map to system fields
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=100, help_text="Name of this mapping configuration")
    data_type = models.CharField(max_length=30, choices=DataType.choices)
    
    # Mapping definition
    field_mappings = models.JSONField(
        default=dict,
        help_text="JSON mapping of Tally field names to system field names"
    )
    
    # Value transformations
    value_transformations = models.JSONField(
        default=dict,
        help_text="Value transformation rules (e.g., Tally 'Dr' -> 'DEBIT')"
    )
    
    # Default values for missing fields
    default_values = models.JSONField(
        default=dict,
        help_text="Default values for fields not in Tally export"
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default mapping for this data type"
    )
    
    class Meta:
        unique_together = ('company', 'name', 'data_type')
        verbose_name = "Tally Field Mapping"
        verbose_name_plural = "Tally Field Mappings"

    def __str__(self):
        return f"{self.name} - {self.get_data_type_display()}"


class TallyImportRecord(BaseModel):
    """
    Individual record from import job
    Tracks each record's import status for debugging and auditing
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    import_job = models.ForeignKey(
        TallyImportJob,
        on_delete=models.CASCADE,
        related_name='records'
    )
    
    data_type = models.CharField(max_length=30, choices=DataType.choices)
    
    # Record identification
    tally_id = models.CharField(max_length=255, blank=True)
    tally_name = models.CharField(max_length=255)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('SKIPPED', 'Skipped'),
            ('DUPLICATE', 'Duplicate'),
        ],
        default='PENDING'
    )
    
    # Source and converted data
    source_data = models.JSONField(default=dict, help_text="Original Tally data")
    converted_data = models.JSONField(default=dict, help_text="Converted system data")
    
    # Result
    created_object_id = models.CharField(max_length=50, blank=True)
    created_object_type = models.CharField(max_length=100, blank=True)
    
    # Error details
    error_message = models.TextField(blank=True)
    validation_errors = models.JSONField(default=list)
    
    # Line number in source file (for reference)
    source_line = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['source_line', 'created_at']
        indexes = [
            models.Index(fields=['import_job', 'status']),
            models.Index(fields=['import_job', 'data_type']),
        ]

    def __str__(self):
        return f"{self.tally_name} - {self.status}"


class TallyMasterMapping(CompanyScopedModel):
    """
    Stores mapping between Tally master IDs and system IDs
    Used for reference during voucher imports
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    import_job = models.ForeignKey(
        TallyImportJob,
        on_delete=models.CASCADE,
        related_name='master_mappings'
    )
    
    data_type = models.CharField(max_length=30, choices=DataType.choices)
    
    # Tally identifiers
    tally_name = models.CharField(max_length=255, db_index=True)
    tally_guid = models.CharField(max_length=100, blank=True)
    
    # System identifiers
    system_id = models.UUIDField()
    system_model = models.CharField(max_length=100)
    
    class Meta:
        unique_together = ('company', 'data_type', 'tally_name')
        indexes = [
            models.Index(fields=['company', 'data_type', 'tally_name']),
        ]

    def __str__(self):
        return f"{self.tally_name} -> {self.system_id}"
