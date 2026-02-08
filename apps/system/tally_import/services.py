"""
Tally Import Service
Handles the actual import of mapped Tally data into the system
"""
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from django.utils import timezone

from .parser import TallyXMLParser
from .mapper import TallyDataMapper
from .models import TallyImportJob, TallyImportRecord, TallyMasterMapping

logger = logging.getLogger(__name__)


class TallyImportService:
    """
    Service class to handle Tally Prime data import
    """
    
    def __init__(self, company_id: str, user_id: str = None):
        """
        Initialize import service
        
        Args:
            company_id: Company ID for the import
            user_id: User performing the import
        """
        self.company_id = company_id
        self.user_id = user_id
        self.import_job = None
        self.parser = None
        self.mapper = None
        self.results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
    
    def create_import_job(self, file_name: str, file_size: int = 0) -> TallyImportJob:
        """Create a new import job record"""
        self.import_job = TallyImportJob.objects.create(
            company_id=self.company_id,
            created_by_id=self.user_id,
            file_name=file_name,
            file_size=file_size,
            status='VALIDATING',
        )
        return self.import_job
    
    def parse_file(self, file_path: str = None, xml_content: str = None) -> Dict:
        """
        Parse Tally XML file and return summary
        
        Args:
            file_path: Path to the Tally XML file
            xml_content: XML content as string
            
        Returns:
            Dictionary with parsing results and summary
        """
        try:
            self.parser = TallyXMLParser(file_path=file_path, xml_content=xml_content)
            
            # Get file info
            tally_info = self.parser.get_tally_info()
            data_types = self.parser.detect_data_types()
            record_counts = self.parser.get_record_counts()
            
            # Update job with file info
            if self.import_job:
                self.import_job.tally_company_name = tally_info.get('company_name', '')
                self.import_job.tally_version = tally_info.get('version', '')
                self.import_job.data_types = data_types
                self.import_job.total_records = sum(record_counts.values())
                self.import_job.save()
            
            return {
                'success': True,
                'tally_info': tally_info,
                'data_types': data_types,
                'record_counts': record_counts,
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            if self.import_job:
                self.import_job.status = 'FAILED'
                self.import_job.error_message = str(e)
                self.import_job.save()
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_data(self, data_types: List[str] = None) -> Dict:
        """
        Validate parsed data before import
        
        Args:
            data_types: List of data types to validate (or all if None)
            
        Returns:
            Validation results
        """
        if not self.parser:
            return {'success': False, 'error': 'No data parsed yet'}
        
        try:
            # Parse all data
            parsed_data = self.parser.get_all_data()
            
            # Create mapper
            self.mapper = TallyDataMapper(self.company_id)
            
            # Map data
            mapped_data = self.mapper.map_all(parsed_data)
            
            # Validate
            is_valid, validation_errors = self.mapper.validate_mapped_data(mapped_data)
            
            # Update job status
            if self.import_job:
                self.import_job.status = 'VALIDATED' if is_valid else 'VALIDATION_FAILED'
                self.import_job.save()
            
            return {
                'success': True,
                'is_valid': is_valid,
                'validation_errors': validation_errors,
                'mapped_data_summary': self.mapper.get_import_summary(),
            }
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def preview_data(self, data_type: str, limit: int = 10) -> List[Dict]:
        """
        Get preview of mapped data
        
        Args:
            data_type: Type of data to preview
            limit: Maximum number of records
            
        Returns:
            List of preview records
        """
        if not self.mapper or not self.mapper.mapped_data:
            return []
        
        data = self.mapper.mapped_data.get(data_type, [])
        return data[:limit]
    
    @transaction.atomic
    def import_data(self, data_types: List[str] = None, 
                   skip_existing: bool = True) -> Dict:
        """
        Import data into the system
        
        Args:
            data_types: List of data types to import (or all if None)
            skip_existing: Skip records that already exist
            
        Returns:
            Import results summary
        """
        if not self.parser:
            return {'success': False, 'error': 'No data parsed yet'}
        
        if not self.mapper:
            # Parse and map data
            parsed_data = self.parser.get_all_data()
            self.mapper = TallyDataMapper(self.company_id)
            self.mapper.map_all(parsed_data)
        
        # Update job status
        if self.import_job:
            self.import_job.status = 'IMPORTING'
            self.import_job.started_at = timezone.now()
            self.import_job.save()
        
        try:
            # Import in order to handle dependencies
            import_order = [
                'ledger_groups',
                'units',
                'godowns',
                'stock_groups',
                'stock_categories',
                'ledgers',
                'stock_items',
                'cost_categories',
                'cost_centers',
                'vouchers',
            ]
            
            results = {}
            
            for data_key in import_order:
                if data_types and data_key not in data_types:
                    continue
                
                if data_key in self.mapper.mapped_data:
                    results[data_key] = self._import_data_type(
                        data_key, 
                        self.mapper.mapped_data[data_key],
                        skip_existing
                    )
            
            # Update job status
            if self.import_job:
                self.import_job.status = 'COMPLETED'
                self.import_job.completed_at = timezone.now()
                self.import_job.imported_records = self.results['success']
                self.import_job.failed_records = self.results['failed']
                self.import_job.skipped_records = self.results['skipped']
                self.import_job.save()
            
            return {
                'success': True,
                'results': results,
                'summary': self.results,
            }
            
        except Exception as e:
            logger.error(f"Import error: {e}")
            if self.import_job:
                self.import_job.status = 'FAILED'
                self.import_job.error_message = str(e)
                self.import_job.save()
            raise
    
    def _import_data_type(self, data_type: str, records: List[Dict], 
                         skip_existing: bool) -> Dict:
        """Import records of a specific type"""
        type_results = {
            'total': len(records),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        import_handlers = {
            'ledger_groups': self._import_ledger_group,
            'ledgers': self._import_ledger,
            'stock_groups': self._import_stock_group,
            'stock_categories': self._import_stock_category,
            'stock_items': self._import_stock_item,
            'units': self._import_unit,
            'godowns': self._import_godown,
            'vouchers': self._import_voucher,
            'cost_centers': self._import_cost_center,
            'cost_categories': self._import_cost_category,
        }
        
        handler = import_handlers.get(data_type)
        if not handler:
            logger.warning(f"No import handler for: {data_type}")
            return type_results
        
        for i, record in enumerate(records):
            try:
                # Create import record
                import_record = None
                if self.import_job:
                    import_record = TallyImportRecord.objects.create(
                        import_job=self.import_job,
                        data_type=data_type.upper().replace('_', ''),
                        tally_name=record.get('name', f'Record_{i}'),
                        tally_guid=record.get('guid', ''),
                        original_data=record,
                    )
                
                # Import the record
                result = handler(record, skip_existing)
                
                if result['status'] == 'success':
                    type_results['success'] += 1
                    self.results['success'] += 1
                    
                    if import_record:
                        import_record.status = 'SUCCESS'
                        import_record.system_id = result.get('system_id')
                        import_record.save()
                    
                    # Store master mapping
                    if result.get('system_id'):
                        self._store_master_mapping(
                            data_type, 
                            record.get('name'),
                            result['system_id']
                        )
                
                elif result['status'] == 'skipped':
                    type_results['skipped'] += 1
                    self.results['skipped'] += 1
                    
                    if import_record:
                        import_record.status = 'SKIPPED'
                        import_record.error_message = result.get('reason', 'Already exists')
                        import_record.save()
                
                else:
                    type_results['failed'] += 1
                    self.results['failed'] += 1
                    error_msg = result.get('error', 'Unknown error')
                    type_results['errors'].append({
                        'record': record.get('name'),
                        'error': error_msg
                    })
                    
                    if import_record:
                        import_record.status = 'FAILED'
                        import_record.error_message = error_msg
                        import_record.save()
                
                # Update job progress
                if self.import_job:
                    self.import_job.processed_records = (
                        self.results['success'] + 
                        self.results['failed'] + 
                        self.results['skipped']
                    )
                    self.import_job.save()
                    
            except Exception as e:
                logger.error(f"Error importing {data_type} record: {e}")
                type_results['failed'] += 1
                self.results['failed'] += 1
                self.results['errors'].append({
                    'type': data_type,
                    'record': record.get('name'),
                    'error': str(e)
                })
        
        return type_results
    
    def _store_master_mapping(self, data_type: str, tally_name: str, system_id: str):
        """Store mapping between Tally name and system ID"""
        if self.import_job and tally_name:
            TallyMasterMapping.objects.update_or_create(
                import_job=self.import_job,
                data_type=data_type.upper(),
                tally_name=tally_name,
                defaults={
                    'system_id': system_id,
                    'company_id': self.company_id,
                }
            )
    
    def _get_system_id(self, data_type: str, tally_name: str) -> Optional[str]:
        """Get system ID for a Tally name"""
        if not tally_name:
            return None
        
        mapping = TallyMasterMapping.objects.filter(
            company_id=self.company_id,
            data_type=data_type.upper(),
            tally_name=tally_name
        ).first()
        
        return mapping.system_id if mapping else None
    
    # ==================== IMPORT HANDLERS ====================
    
    def _import_ledger_group(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a ledger group (account group)"""
        from apps.accounting.models import AccountGroup
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = AccountGroup.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            # Update existing
            for field, value in record.items():
                if field != 'company_id' and hasattr(existing, field) and value is not None:
                    setattr(existing, field, value)
            existing.save()
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Get parent group if specified
        parent_id = None
        parent_name = record.get('parent_name')
        if parent_name:
            parent_id = self._get_system_id('ledger_groups', parent_name)
        
        # Create new
        try:
            group = AccountGroup.objects.create(
                company_id=self.company_id,
                name=name,
                parent_id=parent_id,
                nature=record.get('nature', 'ASSET'),
                description=record.get('description', ''),
            )
            return {'status': 'success', 'system_id': str(group.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_ledger(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a ledger (account/party)"""
        from apps.accounting.models import Account
        from apps.party.models import Party
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Determine if this is a party
        if record.get('is_party'):
            return self._import_party(record, skip_existing)
        
        # Check if account exists
        existing = Account.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            # Update existing
            for field, value in record.items():
                if field not in ['company_id', 'is_party', 'party_type'] and hasattr(existing, field) and value is not None:
                    setattr(existing, field, value)
            existing.save()
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Get account group
        group_name = record.get('account_group')
        group_id = self._get_system_id('ledger_groups', group_name) if group_name else None
        
        # Create new account
        try:
            account = Account.objects.create(
                company_id=self.company_id,
                name=name,
                account_group_id=group_id,
                opening_balance=record.get('opening_balance', Decimal('0')),
                is_bank_account=record.get('is_bank_account', False),
                is_cash_account=record.get('is_cash_account', False),
            )
            return {'status': 'success', 'system_id': str(account.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_party(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a party (customer/vendor)"""
        from apps.party.models import Party
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = Party.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            # Update existing
            self._update_party_fields(existing, record)
            existing.save()
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Create new party
        try:
            party = Party.objects.create(
                company_id=self.company_id,
                name=name,
                party_type=record.get('party_type', 'CUSTOMER'),
                gstin=record.get('gstin'),
                pan=record.get('pan'),
                address=record.get('address'),
                state=record.get('state'),
                country=record.get('country', 'India'),
                pincode=record.get('pincode'),
                email=record.get('email'),
                phone=record.get('phone') or record.get('mobile'),
                credit_period=record.get('credit_period'),
                credit_limit=record.get('credit_limit'),
                opening_balance=record.get('opening_balance', Decimal('0')),
            )
            return {'status': 'success', 'system_id': str(party.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _update_party_fields(self, party, record: Dict):
        """Update party fields from record"""
        field_map = {
            'gstin': 'gstin',
            'pan': 'pan',
            'address': 'address',
            'state': 'state',
            'country': 'country',
            'pincode': 'pincode',
            'email': 'email',
            'phone': 'phone',
            'credit_period': 'credit_period',
            'credit_limit': 'credit_limit',
        }
        for record_field, party_field in field_map.items():
            value = record.get(record_field)
            if value is not None and hasattr(party, party_field):
                setattr(party, party_field, value)
    
    def _import_stock_group(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a stock group (product category)"""
        from apps.products.models import Category
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = Category.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Get parent if specified
        parent_id = None
        parent_name = record.get('parent_name')
        if parent_name:
            parent_id = self._get_system_id('stock_groups', parent_name)
        
        # Create new
        try:
            category = Category.objects.create(
                company_id=self.company_id,
                name=name,
                parent_id=parent_id,
            )
            return {'status': 'success', 'system_id': str(category.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_stock_category(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a stock category"""
        # Use same handler as stock group
        return self._import_stock_group(record, skip_existing)
    
    def _import_stock_item(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a stock item (product)"""
        from apps.products.models import Product
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = Product.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            # Update existing
            self._update_product_fields(existing, record)
            existing.save()
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Get category
        category_id = None
        category_name = record.get('category')
        if category_name:
            category_id = self._get_system_id('stock_groups', category_name)
        
        # Create new product
        try:
            product = Product.objects.create(
                company_id=self.company_id,
                name=name,
                category_id=category_id,
                hsn_code=record.get('hsn_code'),
                gst_rate=record.get('gst_rate'),
                unit=record.get('unit'),
                opening_stock=record.get('opening_stock', Decimal('0')),
                cost_price=record.get('cost_price', Decimal('0')),
                selling_price=record.get('selling_price', Decimal('0')),
                description=record.get('description', ''),
                is_active=record.get('is_active', True),
            )
            return {'status': 'success', 'system_id': str(product.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _update_product_fields(self, product, record: Dict):
        """Update product fields from record"""
        fields = ['hsn_code', 'gst_rate', 'unit', 'cost_price', 'selling_price', 'description']
        for field in fields:
            value = record.get(field)
            if value is not None and hasattr(product, field):
                setattr(product, field, value)
    
    def _import_unit(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a unit of measure"""
        from apps.products.models import Unit
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = Unit.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Create new
        try:
            unit = Unit.objects.create(
                company_id=self.company_id,
                name=name,
                symbol=record.get('symbol', name),
            )
            return {'status': 'success', 'system_id': str(unit.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_godown(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a godown (warehouse)"""
        from apps.inventory.models import Warehouse
        
        name = record.get('name')
        if not name:
            return {'status': 'failed', 'error': 'Name is required'}
        
        # Check if exists
        existing = Warehouse.objects.filter(
            company_id=self.company_id,
            name__iexact=name
        ).first()
        
        if existing:
            if skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
            return {'status': 'success', 'system_id': str(existing.id)}
        
        # Create new
        try:
            warehouse = Warehouse.objects.create(
                company_id=self.company_id,
                name=name,
                address=record.get('address', ''),
            )
            return {'status': 'success', 'system_id': str(warehouse.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_voucher(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a voucher"""
        from apps.voucher.models import Voucher, VoucherLine
        
        voucher_number = record.get('voucher_number')
        voucher_type = record.get('voucher_type')
        voucher_date = record.get('date')
        
        if not voucher_date:
            return {'status': 'failed', 'error': 'Date is required'}
        
        # Check if exists
        if voucher_number:
            existing = Voucher.objects.filter(
                company_id=self.company_id,
                voucher_number=voucher_number,
                voucher_type=voucher_type
            ).first()
            
            if existing and skip_existing:
                return {'status': 'skipped', 'reason': 'Already exists', 'system_id': str(existing.id)}
        
        # Get party
        party_id = None
        party_name = record.get('party')
        if party_name:
            party_id = self._get_system_id('ledgers', party_name)
        
        # Create voucher
        try:
            voucher = Voucher.objects.create(
                company_id=self.company_id,
                voucher_number=voucher_number,
                voucher_type=voucher_type,
                date=voucher_date,
                party_id=party_id,
                reference=record.get('reference'),
                narration=record.get('narration'),
                place_of_supply=record.get('place_of_supply'),
            )
            
            # Create voucher entries
            entries = record.get('entries', [])
            for entry in entries:
                account_id = self._get_system_id('ledgers', entry.get('account_name'))
                if account_id:
                    VoucherLine.objects.create(
                        voucher=voucher,
                        account_id=account_id,
                        debit=entry['amount'] if entry.get('is_debit') else Decimal('0'),
                        credit=entry['amount'] if not entry.get('is_debit') else Decimal('0'),
                        narration=entry.get('narration', ''),
                    )
            
            return {'status': 'success', 'system_id': str(voucher.id)}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _import_cost_center(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a cost center"""
        # Placeholder - implement based on your cost center model
        return {'status': 'skipped', 'reason': 'Cost centers not implemented'}
    
    def _import_cost_category(self, record: Dict, skip_existing: bool) -> Dict:
        """Import a cost category"""
        # Placeholder - implement based on your cost category model
        return {'status': 'skipped', 'reason': 'Cost categories not implemented'}


def process_tally_import(company_id: str, user_id: str, file_path: str = None,
                        xml_content: str = None, data_types: List[str] = None,
                        skip_existing: bool = True) -> Dict:
    """
    Main function to process Tally import
    
    Args:
        company_id: Company ID
        user_id: User ID
        file_path: Path to Tally XML file
        xml_content: XML content as string
        data_types: Types to import (or all if None)
        skip_existing: Skip existing records
        
    Returns:
        Import results
    """
    service = TallyImportService(company_id, user_id)
    
    # Create import job
    file_name = file_path.split('/')[-1] if file_path else 'uploaded_data.xml'
    service.create_import_job(file_name)
    
    # Parse file
    parse_result = service.parse_file(file_path=file_path, xml_content=xml_content)
    if not parse_result['success']:
        return parse_result
    
    # Validate data
    validation_result = service.validate_data(data_types)
    if not validation_result['success']:
        return validation_result
    
    # Import data
    import_result = service.import_data(data_types, skip_existing)
    
    return import_result
