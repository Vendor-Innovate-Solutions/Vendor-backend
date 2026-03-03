"""
Admin configuration for Tally Import
"""
from django.contrib import admin
from .models import TallyImportJob, TallyFieldMapping, TallyImportRecord, TallyMasterMapping


@admin.register(TallyImportJob)
class TallyImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'original_filename', 'status', 'total_records',
                   'processed_records', 'failed_records', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['original_filename', 'tally_company_name']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at']


@admin.register(TallyFieldMapping)
class TallyFieldMappingAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'data_type', 'is_default']
    list_filter = ['data_type', 'is_default']
    search_fields = ['name']


@admin.register(TallyImportRecord)
class TallyImportRecordAdmin(admin.ModelAdmin):
    list_display = ['import_job', 'data_type', 'tally_name', 'status', 'created_at']
    list_filter = ['status', 'data_type']
    search_fields = ['tally_name', 'tally_guid']
    readonly_fields = ['id', 'created_at']


@admin.register(TallyMasterMapping)
class TallyMasterMappingAdmin(admin.ModelAdmin):
    list_display = ['company', 'data_type', 'tally_name', 'system_id', 'created_at']
    list_filter = ['data_type', 'company']
    search_fields = ['tally_name', 'tally_guid', 'system_id']
    readonly_fields = ['id', 'created_at']
