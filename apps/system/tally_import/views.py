"""
API Views for Tally Import
"""
import os
import tempfile
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import default_storage
from django.conf import settings

from .models import TallyImportJob, TallyFieldMapping, TallyImportRecord, TallyMasterMapping
from .serializers import (
    TallyImportJobSerializer,
    TallyFieldMappingSerializer,
    TallyImportRecordSerializer,
    TallyMasterMappingSerializer,
    FileUploadSerializer,
    ImportPreviewSerializer,
    ImportExecuteSerializer,
    FieldMappingConfigSerializer,
)
from .services import TallyImportService
from .parser import TallyXMLParser

logger = logging.getLogger(__name__)


class TallyImportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tally Import operations
    
    Provides endpoints for:
    - Uploading Tally XML files
    - Previewing data before import
    - Configuring field mappings
    - Executing the import
    - Viewing import history and status
    """
    
    serializer_class = TallyImportJobSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_queryset(self):
        """Filter jobs by company"""
        company_id = self.request.headers.get('X-Company-ID') or self.request.query_params.get('company_id')
        if company_id:
            return TallyImportJob.objects.filter(company_id=company_id).order_by('-created_at')
        return TallyImportJob.objects.none()
    
    def get_company_id(self):
        """Get company ID from request"""
        return self.request.headers.get('X-Company-ID') or self.request.query_params.get('company_id')
    
    @action(detail=False, methods=['post'], url_path='upload')
    def upload_file(self, request):
        """
        Upload and parse a Tally XML file
        
        POST /api/tally-import/upload/
        Content-Type: multipart/form-data
        
        Request Body:
            - file: The Tally XML file
            - data_types: (optional) List of data types to import
            - skip_existing: (optional) Whether to skip existing records (default: true)
        
        Response:
            - job_id: UUID of the created import job
            - tally_info: Information about the Tally export
            - data_types: Types of data found in the file
            - record_counts: Count of records by type
        """
        company_id = self.get_company_id()
        if not company_id:
            return Response(
                {'error': 'Company ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = serializer.validated_data['file']
        
        # Validate file extension
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext not in ['.xml', '.txt']:
            return Response(
                {'error': 'Invalid file type. Only XML files are supported.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Read file content
            xml_content = uploaded_file.read().decode('utf-8')
            
            # Create import service
            service = TallyImportService(
                company_id=company_id,
                user_id=str(request.user.id)
            )
            
            # Create import job
            job = service.create_import_job(
                file_name=uploaded_file.name,
                file_size=uploaded_file.size
            )
            
            # Parse the file
            parse_result = service.parse_file(xml_content=xml_content)
            
            if not parse_result['success']:
                return Response(
                    {'error': parse_result.get('error', 'Parse failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate the data
            validation_result = service.validate_data()
            
            # Store parsed data in cache/session for later use
            # In production, you might want to store this in Redis or the database
            request.session[f'tally_import_{job.id}'] = {
                'xml_content': xml_content,
            }
            
            return Response({
                'job_id': str(job.id),
                'tally_info': parse_result.get('tally_info', {}),
                'data_types': parse_result.get('data_types', []),
                'record_counts': parse_result.get('record_counts', {}),
                'validation': validation_result,
            })
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='preview')
    def preview_data(self, request, pk=None):
        """
        Preview parsed data before import
        
        GET /api/tally-import/{job_id}/preview/?data_type=ledgers&limit=10
        
        Query Parameters:
            - data_type: Type of data to preview (ledgers, stock_items, etc.)
            - limit: Maximum number of records to return (default: 10)
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        data_type = request.query_params.get('data_type', 'ledgers')
        limit = int(request.query_params.get('limit', 10))
        
        # Get cached data
        cached_data = request.session.get(f'tally_import_{pk}')
        if not cached_data:
            return Response(
                {'error': 'Import data not found. Please re-upload the file.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Re-parse and get preview
            service = TallyImportService(company_id=company_id)
            service.parse_file(xml_content=cached_data['xml_content'])
            service.validate_data()
            
            preview = service.preview_data(data_type, limit)
            
            return Response({
                'data_type': data_type,
                'count': len(preview),
                'records': preview,
            })
            
        except Exception as e:
            logger.error(f"Preview error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='execute')
    def execute_import(self, request, pk=None):
        """
        Execute the import
        
        POST /api/tally-import/{job_id}/execute/
        
        Request Body:
            - data_types: (optional) List of data types to import
            - skip_existing: (optional) Whether to skip existing records (default: true)
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if job.status in ['IMPORTING', 'COMPLETED']:
            return Response(
                {'error': f'Import already {job.status.lower()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ImportExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data_types = serializer.validated_data.get('data_types')
        skip_existing = serializer.validated_data.get('skip_existing', True)
        
        # Get cached data
        cached_data = request.session.get(f'tally_import_{pk}')
        if not cached_data:
            return Response(
                {'error': 'Import data not found. Please re-upload the file.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create import service
            service = TallyImportService(
                company_id=company_id,
                user_id=str(request.user.id)
            )
            service.import_job = job
            
            # Parse and import
            service.parse_file(xml_content=cached_data['xml_content'])
            result = service.import_data(data_types, skip_existing)
            
            # Clear cached data
            del request.session[f'tally_import_{pk}']
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Import execution error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='status')
    def import_status(self, request, pk=None):
        """
        Get import job status
        
        GET /api/tally-import/{job_id}/status/
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
            serializer = TallyImportJobSerializer(job)
            return Response(serializer.data)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'], url_path='records')
    def import_records(self, request, pk=None):
        """
        Get import records for a job
        
        GET /api/tally-import/{job_id}/records/?status=FAILED&data_type=LEDGER
        
        Query Parameters:
            - status: Filter by status (SUCCESS, FAILED, SKIPPED)
            - data_type: Filter by data type
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        records = TallyImportRecord.objects.filter(import_job=job)
        
        # Apply filters
        record_status = request.query_params.get('status')
        if record_status:
            records = records.filter(status=record_status.upper())
        
        data_type = request.query_params.get('data_type')
        if data_type:
            records = records.filter(data_type=data_type.upper())
        
        # Paginate
        page_size = int(request.query_params.get('page_size', 50))
        page = int(request.query_params.get('page', 1))
        offset = (page - 1) * page_size
        
        total = records.count()
        records = records[offset:offset + page_size]
        
        serializer = TallyImportRecordSerializer(records, many=True)
        
        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'records': serializer.data,
        })
    
    @action(detail=True, methods=['get'], url_path='mappings')
    def get_mappings(self, request, pk=None):
        """
        Get master mappings for a job
        
        GET /api/tally-import/{job_id}/mappings/
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        mappings = TallyMasterMapping.objects.filter(import_job=job)
        serializer = TallyMasterMappingSerializer(mappings, many=True)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='field-mappings')
    def get_field_mapping_options(self, request):
        """
        Get available field mappings for each data type
        
        GET /api/tally-import/field-mappings/
        """
        from .mapper import TallyDataMapper
        
        mapper = TallyDataMapper(company_id='')
        
        return Response({
            'ledger_groups': mapper.DEFAULT_LEDGER_GROUP_MAPPING,
            'ledgers': mapper.DEFAULT_LEDGER_MAPPING,
            'stock_groups': mapper.DEFAULT_STOCK_GROUP_MAPPING,
            'stock_items': mapper.DEFAULT_STOCK_ITEM_MAPPING,
            'vouchers': mapper.DEFAULT_VOUCHER_MAPPING,
        })
    
    @action(detail=True, methods=['post'], url_path='configure-mappings')
    def configure_field_mappings(self, request, pk=None):
        """
        Configure custom field mappings for an import job
        
        POST /api/tally-import/{job_id}/configure-mappings/
        
        Request Body:
            - mappings: List of mapping configurations
        """
        company_id = self.get_company_id()
        
        try:
            job = TallyImportJob.objects.get(id=pk, company_id=company_id)
        except TallyImportJob.DoesNotExist:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = FieldMappingConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        mappings = serializer.validated_data.get('mappings', [])
        
        # Save mappings
        for mapping in mappings:
            TallyFieldMapping.objects.update_or_create(
                import_job=job,
                data_type=mapping.get('data_type'),
                tally_field=mapping.get('tally_field'),
                defaults={
                    'system_field': mapping.get('system_field'),
                    'transformation': mapping.get('transformation'),
                    'is_active': True,
                }
            )
        
        return Response({'message': 'Mappings saved successfully'})


class TallyFieldMappingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing field mappings"""
    
    serializer_class = TallyFieldMappingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        job_id = self.request.query_params.get('job_id')
        if job_id:
            return TallyFieldMapping.objects.filter(import_job_id=job_id)
        return TallyFieldMapping.objects.none()
