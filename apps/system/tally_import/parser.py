"""
Tally Prime XML Parser Service
Parses Tally Prime export files and extracts data for import
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
import re
import logging

logger = logging.getLogger(__name__)


class TallyXMLParser:
    """
    Parser for Tally Prime XML export files
    Handles various Tally export formats including Masters and Vouchers
    """
    
    # Tally date format (YYYYMMDD)
    TALLY_DATE_FORMAT = "%Y%m%d"
    
    # Tally XML namespaces
    NAMESPACES = {
        'tally': 'http://www.tallysolutions.com'
    }
    
    def __init__(self, file_path: str = None, xml_content: str = None):
        """
        Initialize parser with either file path or XML content
        """
        self.file_path = file_path
        self.xml_content = xml_content
        self.root = None
        self.tally_info = {}
        self._parse()
    
    def _parse(self):
        """Parse the XML file/content"""
        try:
            if self.file_path:
                self.tree = ET.parse(self.file_path)
                self.root = self.tree.getroot()
            elif self.xml_content:
                self.root = ET.fromstring(self.xml_content)
            else:
                raise ValueError("Either file_path or xml_content must be provided")
            
            self._extract_tally_info()
        except ET.ParseError as e:
            logger.error(f"XML Parse Error: {e}")
            raise ValueError(f"Invalid XML format: {e}")
    
    def _extract_tally_info(self):
        """Extract Tally company and version information"""
        # Try to find TALLYMESSAGE or ENVELOPE
        envelope = self.root.find('.//ENVELOPE') or self.root
        
        # Extract company name
        company = envelope.find('.//COMPANY') or envelope.find('.//SVCURRENTCOMPANY')
        if company is not None:
            self.tally_info['company_name'] = company.text or ''
        
        # Extract Tally version
        version = envelope.find('.//TALLYVERSION')
        if version is not None:
            self.tally_info['version'] = version.text or ''
        
        # Extract export date
        export_date = envelope.find('.//EXPORTDATE')
        if export_date is not None:
            self.tally_info['export_date'] = self._parse_date(export_date.text)
    
    def get_tally_info(self) -> Dict[str, Any]:
        """Get Tally file information"""
        return self.tally_info
    
    # ==================== DATE/NUMBER PARSING ====================
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse Tally date format (YYYYMMDD)"""
        if not date_str:
            return None
        try:
            # Clean the date string
            date_str = date_str.strip()
            if len(date_str) == 8:
                return datetime.strptime(date_str, self.TALLY_DATE_FORMAT).date()
            return None
        except (ValueError, TypeError):
            return None
    
    def _parse_decimal(self, value: str) -> Decimal:
        """Parse Tally decimal values (may have negative sign at end)"""
        if not value:
            return Decimal('0')
        try:
            value = value.strip()
            # Tally sometimes puts Dr/Cr suffix
            value = re.sub(r'\s*(Dr|Cr)$', '', value, flags=re.IGNORECASE)
            # Handle negative values (Tally may show as "1000-" or "-1000")
            if value.endswith('-'):
                value = '-' + value[:-1]
            return Decimal(value.replace(',', ''))
        except Exception:
            return Decimal('0')
    
    def _parse_bool(self, value: str) -> bool:
        """Parse Tally boolean values"""
        if not value:
            return False
        return value.strip().upper() in ('YES', 'TRUE', '1', 'Y')
    
    def _get_text(self, element: ET.Element, path: str, default: str = '') -> str:
        """Safely get text from element"""
        if element is None:
            return default
        el = element.find(path)
        return (el.text or default) if el is not None else default
    
    # ==================== MASTER DATA PARSING ====================
    
    def parse_ledger_groups(self) -> List[Dict[str, Any]]:
        """
        Parse Ledger Groups (Account Groups) from Tally XML
        Returns list of group dictionaries
        """
        groups = []
        
        # Find all GROUP elements
        for group in self.root.findall('.//GROUP'):
            group_data = {
                'tally_name': self._get_text(group, 'NAME') or group.get('NAME', ''),
                'parent': self._get_text(group, 'PARENT'),
                'is_revenue': self._parse_bool(self._get_text(group, 'ISREVENUE')),
                'is_deemedpositive': self._parse_bool(self._get_text(group, 'ISDEEMEDPOSITIVE')),
                'affects_gross_profit': self._parse_bool(self._get_text(group, 'AFFECTSGROSSPROFIT')),
                'sort_position': self._get_text(group, 'SORTPOSITION'),
                'guid': group.get('GUID', ''),
            }
            
            # Determine nature based on Tally flags
            group_data['nature'] = self._determine_group_nature(group_data)
            groups.append(group_data)
        
        return groups
    
    def _determine_group_nature(self, group_data: Dict) -> str:
        """Determine account nature from Tally group flags"""
        parent = group_data.get('parent', '').upper()
        
        # Map Tally reserved groups to nature
        if parent in ['CAPITAL ACCOUNT', 'RESERVES & SURPLUS', 'SHARE CAPITAL']:
            return 'EQUITY'
        elif parent in ['CURRENT LIABILITIES', 'LOANS (LIABILITY)', 'BRANCH / DIVISIONS', 
                       'SUSPENSE A/C', 'BANK OD A/C']:
            return 'LIABILITY'
        elif parent in ['CURRENT ASSETS', 'FIXED ASSETS', 'INVESTMENTS', 'LOANS & ADVANCES (ASSET)',
                       'MISC. EXPENSES (ASSET)', 'STOCK-IN-HAND', 'DEPOSITS (ASSET)']:
            return 'ASSET'
        elif parent in ['DIRECT INCOMES', 'INDIRECT INCOMES', 'SALES ACCOUNTS']:
            return 'INCOME'
        elif parent in ['DIRECT EXPENSES', 'INDIRECT EXPENSES', 'PURCHASE ACCOUNTS']:
            return 'EXPENSE'
        
        # Use Tally flags as fallback
        if group_data.get('is_revenue'):
            return 'INCOME' if group_data.get('is_deemedpositive') else 'EXPENSE'
        else:
            return 'ASSET' if group_data.get('is_deemedpositive') else 'LIABILITY'
    
    def parse_ledgers(self) -> List[Dict[str, Any]]:
        """
        Parse Ledgers from Tally XML
        Returns list of ledger dictionaries
        """
        ledgers = []
        
        for ledger in self.root.findall('.//LEDGER'):
            ledger_data = {
                'tally_name': self._get_text(ledger, 'NAME') or ledger.get('NAME', ''),
                'parent_group': self._get_text(ledger, 'PARENT'),
                'opening_balance': self._parse_decimal(self._get_text(ledger, 'OPENINGBALANCE')),
                'closing_balance': self._parse_decimal(self._get_text(ledger, 'CLOSINGBALANCE')),
                'is_bill_wise': self._parse_bool(self._get_text(ledger, 'ISBILLWISEON')),
                'is_cost_centres_on': self._parse_bool(self._get_text(ledger, 'ISCOSTCENTRESON')),
                'affects_stock': self._parse_bool(self._get_text(ledger, 'AFFECTSSTOCK')),
                'guid': ledger.get('GUID', ''),
                
                # Party details
                'address': self._get_multiline_text(ledger, 'ADDRESS.LIST/ADDRESS'),
                'state': self._get_text(ledger, 'LEDSTATENAME'),
                'country': self._get_text(ledger, 'COUNTRYNAME'),
                'pincode': self._get_text(ledger, 'PINCODE'),
                'email': self._get_text(ledger, 'EMAIL'),
                'phone': self._get_text(ledger, 'LEDGERPHONE'),
                'mobile': self._get_text(ledger, 'LEDGERMOBILE'),
                
                # GST details
                'gstin': self._get_text(ledger, 'PARTYGSTIN'),
                'gst_registration_type': self._get_text(ledger, 'GSTREGISTRATIONTYPE'),
                'pan': self._get_text(ledger, 'INCOMETAXNUMBER'),
                
                # Bank details
                'bank_name': self._get_text(ledger, 'BANKNAME'),
                'bank_account_number': self._get_text(ledger, 'BANKACCHOLDER.LIST/BANKACCHOLDER'),
                'ifsc_code': self._get_text(ledger, 'IFSCODE'),
                
                # Credit terms
                'credit_period': self._get_text(ledger, 'CREDITPERIOD'),
                'credit_limit': self._parse_decimal(self._get_text(ledger, 'CREDITLIMIT')),
            }
            
            # Determine account type
            ledger_data['account_type'] = self._determine_account_type(ledger_data)
            
            # Parse bill-wise details if available
            ledger_data['bills'] = self._parse_ledger_bills(ledger)
            
            ledgers.append(ledger_data)
        
        return ledgers
    
    def _get_multiline_text(self, element: ET.Element, path: str) -> str:
        """Get multiline text (like addresses)"""
        parts = path.split('/')
        current = element
        for part in parts[:-1]:
            current = current.find(part) if current is not None else None
        
        if current is None:
            return ''
        
        texts = []
        for addr in current.findall(parts[-1]):
            if addr.text:
                texts.append(addr.text.strip())
        return '\n'.join(texts)
    
    def _determine_account_type(self, ledger_data: Dict) -> str:
        """Determine account type from Tally ledger data"""
        parent = ledger_data.get('parent_group', '').upper()
        
        if parent in ['BANK ACCOUNTS', 'BANK OD A/C']:
            return 'BANK'
        elif parent in ['CASH-IN-HAND']:
            return 'CASH'
        elif parent in ['SUNDRY DEBTORS']:
            return 'CUSTOMER'
        elif parent in ['SUNDRY CREDITORS']:
            return 'SUPPLIER'
        elif parent in ['DUTIES & TAXES']:
            return 'TAX'
        elif 'EXPENSE' in parent:
            return 'EXPENSE'
        elif 'INCOME' in parent or 'SALES' in parent:
            return 'INCOME'
        elif 'ASSET' in parent or 'FIXED ASSETS' in parent:
            return 'ASSET'
        elif 'LIABILITY' in parent or 'CAPITAL' in parent:
            return 'LIABILITY'
        
        return 'GENERAL'
    
    def _parse_ledger_bills(self, ledger: ET.Element) -> List[Dict]:
        """Parse bill-wise details for a ledger"""
        bills = []
        for bill in ledger.findall('.//BILLALLOCATIONS.LIST/BILLALLOCATIONS'):
            bills.append({
                'name': self._get_text(bill, 'NAME'),
                'type': self._get_text(bill, 'BILLTYPE'),
                'amount': self._parse_decimal(self._get_text(bill, 'AMOUNT')),
            })
        return bills
    
    # ==================== STOCK/INVENTORY PARSING ====================
    
    def parse_stock_groups(self) -> List[Dict[str, Any]]:
        """Parse Stock Groups from Tally XML"""
        groups = []
        
        for group in self.root.findall('.//STOCKGROUP'):
            groups.append({
                'tally_name': self._get_text(group, 'NAME') or group.get('NAME', ''),
                'parent': self._get_text(group, 'PARENT'),
                'is_addable': self._parse_bool(self._get_text(group, 'ISADDABLE')),
                'guid': group.get('GUID', ''),
            })
        
        return groups
    
    def parse_stock_categories(self) -> List[Dict[str, Any]]:
        """Parse Stock Categories from Tally XML"""
        categories = []
        
        for cat in self.root.findall('.//STOCKCATEGORY'):
            categories.append({
                'tally_name': self._get_text(cat, 'NAME') or cat.get('NAME', ''),
                'parent': self._get_text(cat, 'PARENT'),
                'guid': cat.get('GUID', ''),
            })
        
        return categories
    
    def parse_units(self) -> List[Dict[str, Any]]:
        """Parse Units of Measure from Tally XML"""
        units = []
        
        for unit in self.root.findall('.//UNIT'):
            units.append({
                'tally_name': self._get_text(unit, 'NAME') or unit.get('NAME', ''),
                'symbol': self._get_text(unit, 'ORIGINALNAME'),
                'is_simple_unit': self._parse_bool(self._get_text(unit, 'ISSIMPLEUNIT')),
                'base_units': self._get_text(unit, 'BASEUNITS'),
                'additional_units': self._get_text(unit, 'ADDITIONALUNITS'),
                'conversion': self._parse_decimal(self._get_text(unit, 'CONVERSION')),
                'guid': unit.get('GUID', ''),
            })
        
        return units
    
    def parse_godowns(self) -> List[Dict[str, Any]]:
        """Parse Godowns (Warehouses) from Tally XML"""
        godowns = []
        
        for godown in self.root.findall('.//GODOWN'):
            godowns.append({
                'tally_name': self._get_text(godown, 'NAME') or godown.get('NAME', ''),
                'parent': self._get_text(godown, 'PARENT'),
                'address': self._get_multiline_text(godown, 'ADDRESS.LIST/ADDRESS'),
                'guid': godown.get('GUID', ''),
            })
        
        return godowns
    
    def parse_stock_items(self) -> List[Dict[str, Any]]:
        """Parse Stock Items from Tally XML"""
        items = []
        
        for item in self.root.findall('.//STOCKITEM'):
            item_data = {
                'tally_name': self._get_text(item, 'NAME') or item.get('NAME', ''),
                'parent_group': self._get_text(item, 'PARENT'),
                'category': self._get_text(item, 'CATEGORY'),
                'base_unit': self._get_text(item, 'BASEUNITS'),
                'additional_unit': self._get_text(item, 'ADDITIONALUNITS'),
                
                # Opening stock
                'opening_quantity': self._parse_decimal(self._get_text(item, 'OPENINGBALANCE')),
                'opening_rate': self._parse_decimal(self._get_text(item, 'OPENINGRATE')),
                'opening_value': self._parse_decimal(self._get_text(item, 'OPENINGVALUE')),
                
                # Rates
                'standard_cost': self._parse_decimal(self._get_text(item, 'STANDARDCOST')),
                'standard_price': self._parse_decimal(self._get_text(item, 'STANDARDPRICE')),
                
                # GST
                'gst_applicable': self._parse_bool(self._get_text(item, 'GSTAPPLICABLE')),
                'hsn_code': self._get_text(item, 'HSNCODE'),
                'gst_rate': self._parse_decimal(self._get_text(item, 'GSTRATE')),
                'igst_rate': self._parse_decimal(self._get_text(item, 'IGSTRATE')),
                'cgst_rate': self._parse_decimal(self._get_text(item, 'CGSTRATE')),
                'sgst_rate': self._parse_decimal(self._get_text(item, 'SGSTRATE')),
                
                # Other details
                'description': self._get_text(item, 'DESCRIPTION'),
                'narration': self._get_text(item, 'NARRATION'),
                'batch_wise': self._parse_bool(self._get_text(item, 'ISBATCHWISEON')),
                'perishable': self._parse_bool(self._get_text(item, 'ISPERISHABLEON')),
                
                'guid': item.get('GUID', ''),
            }
            
            # Parse batch details
            item_data['batches'] = self._parse_stock_batches(item)
            
            # Parse godown-wise stock
            item_data['godown_stock'] = self._parse_godown_stock(item)
            
            items.append(item_data)
        
        return items
    
    def _parse_stock_batches(self, item: ET.Element) -> List[Dict]:
        """Parse batch details for a stock item"""
        batches = []
        for batch in item.findall('.//BATCHALLOCATIONS.LIST/BATCHALLOCATIONS'):
            batches.append({
                'name': self._get_text(batch, 'BATCHNAME'),
                'godown': self._get_text(batch, 'GODOWNNAME'),
                'quantity': self._parse_decimal(self._get_text(batch, 'BILLEDQTY')),
                'rate': self._parse_decimal(self._get_text(batch, 'RATE')),
                'amount': self._parse_decimal(self._get_text(batch, 'AMOUNT')),
                'mfg_date': self._parse_date(self._get_text(batch, 'MFGDATE')),
                'expiry_date': self._parse_date(self._get_text(batch, 'EXPIRYDATE')),
            })
        return batches
    
    def _parse_godown_stock(self, item: ET.Element) -> List[Dict]:
        """Parse godown-wise stock for a stock item"""
        godown_stock = []
        for stock in item.findall('.//GODOWNSTOCKENTRY.LIST/GODOWNSTOCKENTRY'):
            godown_stock.append({
                'godown': self._get_text(stock, 'GODOWNNAME'),
                'quantity': self._parse_decimal(self._get_text(stock, 'BILLEDQTY')),
                'rate': self._parse_decimal(self._get_text(stock, 'RATE')),
                'amount': self._parse_decimal(self._get_text(stock, 'AMOUNT')),
            })
        return godown_stock
    
    # ==================== VOUCHER PARSING ====================
    
    def parse_vouchers(self) -> List[Dict[str, Any]]:
        """Parse Vouchers from Tally XML"""
        vouchers = []
        
        for voucher in self.root.findall('.//VOUCHER'):
            voucher_data = {
                'tally_name': self._get_text(voucher, 'VOUCHERNUMBER') or voucher.get('VCHKEY', ''),
                'voucher_number': self._get_text(voucher, 'VOUCHERNUMBER'),
                'voucher_type': self._get_text(voucher, 'VOUCHERTYPENAME'),
                'date': self._parse_date(self._get_text(voucher, 'DATE')),
                'reference_number': self._get_text(voucher, 'REFERENCE'),
                'reference_date': self._parse_date(self._get_text(voucher, 'REFERENCEDATE')),
                'narration': self._get_text(voucher, 'NARRATION'),
                'party_name': self._get_text(voucher, 'PARTYNAME'),
                
                # Flags
                'is_invoice': self._parse_bool(self._get_text(voucher, 'ISINVOICE')),
                'is_cancelled': self._parse_bool(self._get_text(voucher, 'ISCANCELLED')),
                'is_optional': self._parse_bool(self._get_text(voucher, 'ISOPTIONAL')),
                
                # GST details
                'place_of_supply': self._get_text(voucher, 'PLACEOFSUPPLY'),
                'gstin': self._get_text(voucher, 'PARTYGSTIN'),
                'gst_registration_type': self._get_text(voucher, 'GSTREGISTRATIONTYPE'),
                
                'guid': voucher.get('GUID', ''),
            }
            
            # Parse ledger entries
            voucher_data['ledger_entries'] = self._parse_ledger_entries(voucher)
            
            # Parse inventory entries
            voucher_data['inventory_entries'] = self._parse_inventory_entries(voucher)
            
            # Parse bill allocations
            voucher_data['bill_allocations'] = self._parse_voucher_bills(voucher)
            
            vouchers.append(voucher_data)
        
        return vouchers
    
    def _parse_ledger_entries(self, voucher: ET.Element) -> List[Dict]:
        """Parse ledger entries (accounting entries) from voucher"""
        entries = []
        
        for entry in voucher.findall('.//ALLLEDGERENTRIES.LIST'):
            entries.append({
                'ledger': self._get_text(entry, 'LEDGERNAME'),
                'amount': self._parse_decimal(self._get_text(entry, 'AMOUNT')),
                'is_debit': self._parse_decimal(self._get_text(entry, 'AMOUNT')) < 0,
                'narration': self._get_text(entry, 'NARRATION'),
            })
        
        # Also check LEDGERENTRIES.LIST
        for entry in voucher.findall('.//LEDGERENTRIES.LIST'):
            entries.append({
                'ledger': self._get_text(entry, 'LEDGERNAME'),
                'amount': self._parse_decimal(self._get_text(entry, 'AMOUNT')),
                'is_debit': self._parse_decimal(self._get_text(entry, 'AMOUNT')) < 0,
                'narration': self._get_text(entry, 'NARRATION'),
            })
        
        return entries
    
    def _parse_inventory_entries(self, voucher: ET.Element) -> List[Dict]:
        """Parse inventory entries from voucher"""
        entries = []
        
        for entry in voucher.findall('.//ALLINVENTORYENTRIES.LIST'):
            entries.append({
                'stock_item': self._get_text(entry, 'STOCKITEMNAME'),
                'quantity': self._parse_decimal(self._get_text(entry, 'ACTUALQTY') or 
                                               self._get_text(entry, 'BILLEDQTY')),
                'rate': self._parse_decimal(self._get_text(entry, 'RATE')),
                'amount': self._parse_decimal(self._get_text(entry, 'AMOUNT')),
                'godown': self._get_text(entry, 'GODOWNNAME'),
                'batch': self._get_text(entry, 'BATCHNAME'),
                'tracking_number': self._get_text(entry, 'TRACKINGNUMBER'),
            })
        
        # Also check INVENTORYENTRIES.LIST
        for entry in voucher.findall('.//INVENTORYENTRIES.LIST'):
            entries.append({
                'stock_item': self._get_text(entry, 'STOCKITEMNAME'),
                'quantity': self._parse_decimal(self._get_text(entry, 'ACTUALQTY') or 
                                               self._get_text(entry, 'BILLEDQTY')),
                'rate': self._parse_decimal(self._get_text(entry, 'RATE')),
                'amount': self._parse_decimal(self._get_text(entry, 'AMOUNT')),
                'godown': self._get_text(entry, 'GODOWNNAME'),
                'batch': self._get_text(entry, 'BATCHNAME'),
            })
        
        return entries
    
    def _parse_voucher_bills(self, voucher: ET.Element) -> List[Dict]:
        """Parse bill allocations from voucher"""
        bills = []
        
        for bill in voucher.findall('.//BILLALLOCATIONS.LIST'):
            bills.append({
                'name': self._get_text(bill, 'NAME'),
                'type': self._get_text(bill, 'BILLTYPE'),
                'amount': self._parse_decimal(self._get_text(bill, 'AMOUNT')),
            })
        
        return bills
    
    # ==================== COST CENTER PARSING ====================
    
    def parse_cost_centers(self) -> List[Dict[str, Any]]:
        """Parse Cost Centers from Tally XML"""
        centers = []
        
        for center in self.root.findall('.//COSTCENTRE'):
            centers.append({
                'tally_name': self._get_text(center, 'NAME') or center.get('NAME', ''),
                'parent': self._get_text(center, 'PARENT'),
                'category': self._get_text(center, 'CATEGORY'),
                'revenue_ledger': self._get_text(center, 'REVENUELEDGERSFOROPBALFOROP'),
                'guid': center.get('GUID', ''),
            })
        
        return centers
    
    def parse_cost_categories(self) -> List[Dict[str, Any]]:
        """Parse Cost Categories from Tally XML"""
        categories = []
        
        for cat in self.root.findall('.//COSTCATEGORY'):
            categories.append({
                'tally_name': self._get_text(cat, 'NAME') or cat.get('NAME', ''),
                'allocate_revenue': self._parse_bool(self._get_text(cat, 'ALLOCATEREVENUE')),
                'allocate_non_revenue': self._parse_bool(self._get_text(cat, 'ALLOCATENONREVENUE')),
                'guid': cat.get('GUID', ''),
            })
        
        return categories
    
    # ==================== SUMMARY/DETECTION ====================
    
    def detect_data_types(self) -> List[str]:
        """Detect what types of data are present in the file"""
        data_types = []
        
        if self.root.findall('.//GROUP'):
            data_types.append('LEDGER_GROUP')
        if self.root.findall('.//LEDGER'):
            data_types.append('LEDGER')
        if self.root.findall('.//STOCKGROUP'):
            data_types.append('STOCK_GROUP')
        if self.root.findall('.//STOCKCATEGORY'):
            data_types.append('STOCK_CATEGORY')
        if self.root.findall('.//STOCKITEM'):
            data_types.append('STOCK_ITEM')
        if self.root.findall('.//UNIT'):
            data_types.append('UNIT')
        if self.root.findall('.//GODOWN'):
            data_types.append('GODOWN')
        if self.root.findall('.//VOUCHER'):
            data_types.append('VOUCHER')
        if self.root.findall('.//COSTCENTRE'):
            data_types.append('COST_CENTER')
        if self.root.findall('.//COSTCATEGORY'):
            data_types.append('COST_CATEGORY')
        
        return data_types
    
    def get_record_counts(self) -> Dict[str, int]:
        """Get count of records by type"""
        return {
            'ledger_groups': len(self.root.findall('.//GROUP')),
            'ledgers': len(self.root.findall('.//LEDGER')),
            'stock_groups': len(self.root.findall('.//STOCKGROUP')),
            'stock_categories': len(self.root.findall('.//STOCKCATEGORY')),
            'stock_items': len(self.root.findall('.//STOCKITEM')),
            'units': len(self.root.findall('.//UNIT')),
            'godowns': len(self.root.findall('.//GODOWN')),
            'vouchers': len(self.root.findall('.//VOUCHER')),
            'cost_centers': len(self.root.findall('.//COSTCENTRE')),
            'cost_categories': len(self.root.findall('.//COSTCATEGORY')),
        }
    
    def get_all_data(self) -> Dict[str, List[Dict]]:
        """Parse and return all data from the file"""
        return {
            'ledger_groups': self.parse_ledger_groups(),
            'ledgers': self.parse_ledgers(),
            'stock_groups': self.parse_stock_groups(),
            'stock_categories': self.parse_stock_categories(),
            'stock_items': self.parse_stock_items(),
            'units': self.parse_units(),
            'godowns': self.parse_godowns(),
            'vouchers': self.parse_vouchers(),
            'cost_centers': self.parse_cost_centers(),
            'cost_categories': self.parse_cost_categories(),
        }
