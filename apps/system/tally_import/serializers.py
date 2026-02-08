"""
Serializers for Tally Import API
"""
from rest_framework import serializers
from .models import TallyImportJob, TallyFieldMapping, TallyImportRecord, TallyMasterMapping


class TallyImportJobSerializer(serializers.ModelSerializer):
    """Serializer for TallyImportJob"""
    
    progress_percentage = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = TallyImportJob
        fields = [
            'id', 'company', 'file_name', 'file_size', 'status',
            'tally_company_name', 'tally_version', 'data_types',
            'total_records', 'processed_records', 'imported_records',
            'failed_records', 'skipped_records', 'error_message',
            'started_at', 'completed_at', 'created_at', 'created_by',
            'progress_percentage', 'duration'
        ]
        read_only_fields = ['id', 'created_at', 'created_by', 'company']
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage"""
        if obj.total_records == 0:
            return 0
        return round((obj.processed_records / obj.total_records) * 100, 2)
    
    def get_duration(self, obj):
        """Calculate import duration in seconds"""
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return delta.total_seconds()
        return None


class TallyFieldMappingSerializer(serializers.ModelSerializer):
    """Serializer for TallyFieldMapping"""
    
    class Meta:
        model = TallyFieldMapping
        fields = [
            'id', 'import_job', 'data_type', 'tally_field',
            'system_field', 'transformation', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TallyImportRecordSerializer(serializers.ModelSerializer):
    """Serializer for TallyImportRecord"""
    
    class Meta:
        model = TallyImportRecord
        fields = [
            'id', 'import_job', 'data_type', 'tally_name',
            'tally_guid', 'status', 'system_id', 'error_message',
            'original_data', 'mapped_data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TallyMasterMappingSerializer(serializers.ModelSerializer):
    """Serializer for TallyMasterMapping"""
    
    class Meta:
        model = TallyMasterMapping
        fields = [
            'id', 'import_job', 'company', 'data_type',
            'tally_name', 'tally_guid', 'system_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FileUploadSerializer(serializers.Serializer):
    """Serializer for file upload"""
    
    file = serializers.FileField()
    data_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of data types to import. If not provided, all types will be imported."
    )
    skip_existing = serializers.BooleanField(
        default=True,
        help_text="Skip records that already exist in the system"
    )


class ImportPreviewSerializer(serializers.Serializer):
    """Serializer for import preview request"""
    
    job_id = serializers.UUIDField()
    data_type = serializers.CharField()
    limit = serializers.IntegerField(default=10, min_value=1, max_value=100)


class ImportExecuteSerializer(serializers.Serializer):
    """Serializer for import execution request"""
    
    job_id = serializers.UUIDField()
    data_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of data types to import. If not provided, all types will be imported."
    )
    skip_existing = serializers.BooleanField(
        default=True,
        help_text="Skip records that already exist in the system"
    )


class FieldMappingConfigSerializer(serializers.Serializer):
    """Serializer for field mapping configuration"""
    
    job_id = serializers.UUIDField()
    mappings = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        help_text="List of field mappings. Each mapping should have: data_type, tally_field, system_field"
    )


class ImportSummarySerializer(serializers.Serializer):
    """Serializer for import summary response"""
    
    success = serializers.BooleanField()
    tally_info = serializers.DictField(required=False)
    data_types = serializers.ListField(child=serializers.CharField(), required=False)
    record_counts = serializers.DictField(required=False)
    validation_errors = serializers.ListField(required=False)
    results = serializers.DictField(required=False)
    summary = serializers.DictField(required=False)
    error = serializers.CharField(required=False)
