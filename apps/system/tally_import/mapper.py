"""
Tally Data Mapper Service
Maps parsed Tally data to the system's models
"""
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from datetime import date
import logging
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class TallyDataMapper:
    """
    Maps Tally Prime data to the system's models
    Handles field mapping, data transformation, and validation
    """
    
    # Default field mappings from Tally to System
    DEFAULT_LEDGER_GROUP_MAPPING = {
        'tally_name': 'name',
        'parent': 'parent_name',
        'nature': 'nature',
    }
    
    DEFAULT_LEDGER_MAPPING = {
        'tally_name': 'name',
        'parent_group': 'account_group',
        'opening_balance': 'opening_balance',
        'gstin': 'gstin',
        'pan': 'pan',
        'address': 'address',
        'state': 'state',
        'country': 'country',
        'pincode': 'pincode',
        'email': 'email',
        'phone': 'phone',
        'mobile': 'mobile',
        'credit_period': 'credit_period',
        'credit_limit': 'credit_limit',
    }
    
    DEFAULT_STOCK_GROUP_MAPPING = {
        'tally_name': 'name',
        'parent': 'parent_name',
    }
    
    DEFAULT_STOCK_ITEM_MAPPING = {
        'tally_name': 'name',
        'parent_group': 'category',
        'base_unit': 'unit',
        'hsn_code': 'hsn_code',
        'gst_rate': 'gst_rate',
        'opening_quantity': 'opening_stock',
        'opening_rate': 'cost_price',
        'standard_price': 'selling_price',
        'description': 'description',
    }
    
    DEFAULT_VOUCHER_MAPPING = {
        'voucher_number': 'voucher_number',
        'voucher_type': 'voucher_type',
        'date': 'date',
        'party_name': 'party',
        'reference_number': 'reference',
        'narration': 'narration',
        'place_of_supply': 'place_of_supply',
    }
    
    # Tally voucher type to system voucher type mapping
    VOUCHER_TYPE_MAPPING = {
        'SALES': 'SALES',
        'PURCHASE': 'PURCHASE',
        'PAYMENT': 'PAYMENT',
        'RECEIPT': 'RECEIPT',
        'CONTRA': 'CONTRA',
        'JOURNAL': 'JOURNAL',
        'CREDIT NOTE': 'CREDIT_NOTE',
        'DEBIT NOTE': 'DEBIT_NOTE',
        'SALES ORDER': 'SALES_ORDER',
        'PURCHASE ORDER': 'PURCHASE_ORDER',
        'DELIVERY NOTE': 'DELIVERY_NOTE',
        'RECEIPT NOTE': 'RECEIPT_NOTE',
        'STOCK JOURNAL': 'STOCK_JOURNAL',
        'PHYSICAL STOCK': 'PHYSICAL_STOCK',
        'MATERIAL IN': 'MATERIAL_IN',
        'MATERIAL OUT': 'MATERIAL_OUT',
    }
    
    # Tally group to system nature mapping
    TALLY_GROUP_NATURE_MAPPING = {
        # Primary Groups
        'CAPITAL ACCOUNT': 'EQUITY',
        'CURRENT ASSETS': 'ASSET',
        'CURRENT LIABILITIES': 'LIABILITY',
        'DIRECT EXPENSES': 'EXPENSE',
        'DIRECT INCOMES': 'INCOME',
        'FIXED ASSETS': 'ASSET',
        'INDIRECT EXPENSES': 'EXPENSE',
        'INDIRECT INCOMES': 'INCOME',
        'INVESTMENTS': 'ASSET',
        'LOANS (LIABILITY)': 'LIABILITY',
        'LOANS & ADVANCES (ASSET)': 'ASSET',
        'MISC. EXPENSES (ASSET)': 'ASSET',
        'SUSPENSE A/C': 'LIABILITY',
        'BRANCH / DIVISIONS': 'LIABILITY',
        'RESERVES & SURPLUS': 'EQUITY',
        'SECURED LOANS': 'LIABILITY',
        'UNSECURED LOANS': 'LIABILITY',
        'PURCHASE ACCOUNTS': 'EXPENSE',
        'SALES ACCOUNTS': 'INCOME',
        
        # Common Sub-Groups
        'BANK ACCOUNTS': 'ASSET',
        'BANK OD A/C': 'LIABILITY',
        'CASH-IN-HAND': 'ASSET',
        'DEPOSITS (ASSET)': 'ASSET',
        'DUTIES & TAXES': 'LIABILITY',
        'PROVISIONS': 'LIABILITY',
        'STOCK-IN-HAND': 'ASSET',
        'SUNDRY CREDITORS': 'LIABILITY',
        'SUNDRY DEBTORS': 'ASSET',
    }
    
    # GST Registration Type Mapping
    GST_REGISTRATION_MAPPING = {
        'REGULAR': 'REGULAR',
        'COMPOSITION': 'COMPOSITION',
        'UNREGISTERED': 'UNREGISTERED',
        'CONSUMER': 'CONSUMER',
        'UNKNOWN': 'UNREGISTERED',
    }
    
    def __init__(self, company_id: str, custom_mappings: Dict = None):
        """
        Initialize mapper with company context
        
        Args:
            company_id: The company ID for the import
            custom_mappings: Optional custom field mappings
        """
        self.company_id = company_id
        self.custom_mappings = custom_mappings or {}
        self.errors = []
        self.warnings = []
        self.mapped_data = {}
        self.master_mapping = {}  # Stores Tally name to System ID mapping
    
    def get_field_mapping(self, data_type: str) -> Dict[str, str]:
        """Get field mapping for a data type, considering custom mappings"""
        default_mappings = {
            'LEDGER_GROUP': self.DEFAULT_LEDGER_GROUP_MAPPING,
            'LEDGER': self.DEFAULT_LEDGER_MAPPING,
            'STOCK_GROUP': self.DEFAULT_STOCK_GROUP_MAPPING,
            'STOCK_ITEM': self.DEFAULT_STOCK_ITEM_MAPPING,
            'VOUCHER': self.DEFAULT_VOUCHER_MAPPING,
        }
        
        mapping = default_mappings.get(data_type, {}).copy()
        
        # Apply custom mappings
        if data_type in self.custom_mappings:
            mapping.update(self.custom_mappings[data_type])
        
        return mapping
    
    def map_record(self, data_type: str, tally_record: Dict) -> Dict:
        """
        Map a single Tally record to system format
        
        Args:
            data_type: Type of record (LEDGER, STOCK_ITEM, etc.)
            tally_record: Parsed Tally record
            
        Returns:
            Mapped record ready for system import
        """
        field_mapping = self.get_field_mapping(data_type)
        mapped = {}
        
        for tally_field, system_field in field_mapping.items():
            if tally_field in tally_record:
                value = tally_record[tally_field]
                
                # Apply transformations
                value = self._transform_value(data_type, system_field, value)
                
                if value is not None:
                    mapped[system_field] = value
        
        # Add company_id
        mapped['company_id'] = self.company_id
        
        # Apply type-specific transformations
        mapped = self._apply_type_transformations(data_type, tally_record, mapped)
        
        return mapped
    
    def _transform_value(self, data_type: str, field: str, value: Any) -> Any:
        """Transform a field value during mapping"""
        if value is None or value == '':
            return None
        
        # GST Registration Type
        if field in ['gst_registration_type', 'registration_type']:
            return self.GST_REGISTRATION_MAPPING.get(str(value).upper(), 'UNREGISTERED')
        
        # Nature field
        if field == 'nature':
            return self.TALLY_GROUP_NATURE_MAPPING.get(str(value).upper(), value)
        
        # Voucher Type
        if field == 'voucher_type':
            return self.VOUCHER_TYPE_MAPPING.get(str(value).upper(), value)
        
        # Boolean conversions
        if isinstance(value, str) and value.upper() in ('YES', 'NO', 'TRUE', 'FALSE'):
            return value.upper() in ('YES', 'TRUE')
        
        # Decimal fields
        if field in ['opening_balance', 'credit_limit', 'gst_rate', 'cost_price', 
                     'selling_price', 'opening_stock', 'quantity', 'rate', 'amount']:
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            elif isinstance(value, str):
                try:
                    return Decimal(value.replace(',', ''))
                except:
                    return Decimal('0')
        
        return value
    
    def _apply_type_transformations(self, data_type: str, tally_record: Dict, 
                                    mapped: Dict) -> Dict:
        """Apply type-specific transformations"""
        
        if data_type == 'LEDGER':
            # Determine if this is a party (customer/vendor)
            parent = tally_record.get('parent_group', '').upper()
            if parent == 'SUNDRY DEBTORS':
                mapped['party_type'] = 'CUSTOMER'
                mapped['is_party'] = True
            elif parent == 'SUNDRY CREDITORS':
                mapped['party_type'] = 'VENDOR'
                mapped['is_party'] = True
            elif parent in ['BANK ACCOUNTS', 'BANK OD A/C']:
                mapped['is_bank_account'] = True
            elif parent == 'CASH-IN-HAND':
                mapped['is_cash_account'] = True
        
        elif data_type == 'STOCK_ITEM':
            # Add default values for stock items
            mapped.setdefault('is_active', True)
            
            # Handle GST rates
            if tally_record.get('gst_rate'):
                mapped['gst_rate'] = tally_record['gst_rate']
            elif tally_record.get('igst_rate'):
                mapped['gst_rate'] = tally_record['igst_rate']
            elif tally_record.get('cgst_rate') and tally_record.get('sgst_rate'):
                mapped['gst_rate'] = tally_record['cgst_rate'] + tally_record['sgst_rate']
        
        elif data_type == 'VOUCHER':
            # Map ledger entries
            if 'ledger_entries' in tally_record:
                mapped['entries'] = self._map_voucher_entries(tally_record['ledger_entries'])
            
            # Map inventory entries
            if 'inventory_entries' in tally_record:
                mapped['items'] = self._map_inventory_entries(tally_record['inventory_entries'])
        
        return mapped
    
    def _map_voucher_entries(self, entries: List[Dict]) -> List[Dict]:
        """Map voucher ledger entries"""
        mapped_entries = []
        for entry in entries:
            mapped = {
                'account_name': entry.get('ledger'),
                'amount': abs(entry.get('amount', 0)),
                'is_debit': entry.get('amount', 0) < 0,  # Tally uses negative for debit
                'narration': entry.get('narration', ''),
            }
            mapped_entries.append(mapped)
        return mapped_entries
    
    def _map_inventory_entries(self, entries: List[Dict]) -> List[Dict]:
        """Map voucher inventory entries"""
        mapped_items = []
        for entry in entries:
            mapped = {
                'item_name': entry.get('stock_item'),
                'quantity': entry.get('quantity', 0),
                'rate': entry.get('rate', 0),
                'amount': abs(entry.get('amount', 0)),
                'warehouse': entry.get('godown'),
                'batch': entry.get('batch'),
            }
            mapped_items.append(mapped)
        return mapped_items
    
    def map_all(self, parsed_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Map all parsed Tally data to system format
        
        Args:
            parsed_data: Dictionary of parsed data by type
            
        Returns:
            Dictionary of mapped data ready for import
        """
        type_mapping = {
            'ledger_groups': 'LEDGER_GROUP',
            'ledgers': 'LEDGER',
            'stock_groups': 'STOCK_GROUP',
            'stock_categories': 'STOCK_CATEGORY',
            'stock_items': 'STOCK_ITEM',
            'units': 'UNIT',
            'godowns': 'GODOWN',
            'vouchers': 'VOUCHER',
            'cost_centers': 'COST_CENTER',
            'cost_categories': 'COST_CATEGORY',
        }
        
        mapped_data = {}
        
        for key, data_type in type_mapping.items():
            if key in parsed_data and parsed_data[key]:
                mapped_data[key] = []
                for record in parsed_data[key]:
                    try:
                        mapped = self.map_record(data_type, record)
                        mapped_data[key].append(mapped)
                    except Exception as e:
                        self.errors.append({
                            'type': data_type,
                            'record': record.get('tally_name', 'Unknown'),
                            'error': str(e)
                        })
        
        self.mapped_data = mapped_data
        return mapped_data
    
    def validate_mapped_data(self, mapped_data: Dict[str, List[Dict]]) -> Tuple[bool, List[Dict]]:
        """
        Validate mapped data before import
        
        Returns:
            Tuple of (is_valid, list of validation errors)
        """
        validation_errors = []
        
        # Validate ledger groups
        if 'ledger_groups' in mapped_data:
            for i, group in enumerate(mapped_data['ledger_groups']):
                if not group.get('name'):
                    validation_errors.append({
                        'type': 'LEDGER_GROUP',
                        'index': i,
                        'field': 'name',
                        'error': 'Name is required'
                    })
        
        # Validate ledgers
        if 'ledgers' in mapped_data:
            for i, ledger in enumerate(mapped_data['ledgers']):
                if not ledger.get('name'):
                    validation_errors.append({
                        'type': 'LEDGER',
                        'index': i,
                        'field': 'name',
                        'error': 'Name is required'
                    })
                
                # Validate GSTIN format if present
                gstin = ledger.get('gstin')
                if gstin and len(gstin) != 15:
                    validation_errors.append({
                        'type': 'LEDGER',
                        'index': i,
                        'record': ledger.get('name'),
                        'field': 'gstin',
                        'error': f'Invalid GSTIN format: {gstin}'
                    })
        
        # Validate stock items
        if 'stock_items' in mapped_data:
            for i, item in enumerate(mapped_data['stock_items']):
                if not item.get('name'):
                    validation_errors.append({
                        'type': 'STOCK_ITEM',
                        'index': i,
                        'field': 'name',
                        'error': 'Name is required'
                    })
                
                # Validate HSN code if present
                hsn = item.get('hsn_code')
                if hsn and len(hsn) not in [4, 6, 8]:
                    validation_errors.append({
                        'type': 'STOCK_ITEM',
                        'index': i,
                        'record': item.get('name'),
                        'field': 'hsn_code',
                        'error': f'Invalid HSN code format: {hsn}'
                    })
        
        # Validate vouchers
        if 'vouchers' in mapped_data:
            for i, voucher in enumerate(mapped_data['vouchers']):
                if not voucher.get('date'):
                    validation_errors.append({
                        'type': 'VOUCHER',
                        'index': i,
                        'field': 'date',
                        'error': 'Date is required'
                    })
                
                if not voucher.get('voucher_type'):
                    validation_errors.append({
                        'type': 'VOUCHER',
                        'index': i,
                        'field': 'voucher_type',
                        'error': 'Voucher type is required'
                    })
        
        is_valid = len(validation_errors) == 0
        return is_valid, validation_errors
    
    def get_import_summary(self) -> Dict:
        """Get summary of mapped data"""
        summary = {
            'total_records': 0,
            'by_type': {},
            'errors': len(self.errors),
            'warnings': len(self.warnings),
        }
        
        for key, records in self.mapped_data.items():
            count = len(records)
            summary['by_type'][key] = count
            summary['total_records'] += count
        
        return summary
    
    def store_master_mapping(self, data_type: str, tally_name: str, system_id: str):
        """Store mapping between Tally name and system ID"""
        if data_type not in self.master_mapping:
            self.master_mapping[data_type] = {}
        self.master_mapping[data_type][tally_name] = system_id
    
    def get_system_id(self, data_type: str, tally_name: str) -> Optional[str]:
        """Get system ID for a Tally name"""
        return self.master_mapping.get(data_type, {}).get(tally_name)
