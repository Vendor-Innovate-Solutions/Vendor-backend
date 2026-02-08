"""
Admin configuration for Tally Import
"""
from django.contrib import admin
from .models import TallyImportJob, TallyFieldMapping, TallyImportRecord, TallyMasterMapping


@admin.register(TallyImportJob)
class TallyImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'file_name', 'status', 'total_records', 
                   'imported_records', 'failed_records', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['file_name', 'tally_company_name']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at']
    
    fieldsets = (
        ('Job Info', {
            'fields': ('id', 'company', 'file_name', 'file_size', 'status')
        }),
        ('Tally Info', {
            'fields': ('tally_company_name', 'tally_version', 'data_types')
        }),
        ('Progress', {
            'fields': ('total_records', 'processed_records', 'imported_records', 
                      'failed_records', 'skipped_records', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at', 'created_by')
        }),
    )


@admin.register(TallyFieldMapping)
class TallyFieldMappingAdmin(admin.ModelAdmin):
    list_display = ['import_job', 'data_type', 'tally_field', 'system_field', 'is_active']
    list_filter = ['data_type', 'is_active']
    search_fields = ['tally_field', 'system_field']


@admin.register(TallyImportRecord)
class TallyImportRecordAdmin(admin.ModelAdmin):
    list_display = ['import_job', 'data_type', 'tally_name', 'status', 'system_id', 'created_at']
    list_filter = ['status', 'data_type']
    search_fields = ['tally_name', 'tally_guid', 'system_id']
    readonly_fields = ['id', 'created_at']


@admin.register(TallyMasterMapping)
class TallyMasterMappingAdmin(admin.ModelAdmin):
    list_display = ['company', 'data_type', 'tally_name', 'system_id', 'created_at']
    list_filter = ['data_type', 'company']
    search_fields = ['tally_name', 'tally_guid', 'system_id']
    readonly_fields = ['id', 'created_at']
