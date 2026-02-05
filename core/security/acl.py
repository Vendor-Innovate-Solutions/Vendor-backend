"""
Access Control List (ACL) and Access Control Matrix Implementation.

This module implements comprehensive access control mechanisms:
- Access Control Matrix with subjects and objects
- Permission levels (READ, WRITE, DELETE, ADMIN)
- Policy-based access control
- Integration with Django's authentication system

Security Requirements Covered:
- Implement Access Control Matrix with minimum 3 subjects and 3 objects
- Policy Definition & Justification
- Implementation of Access Control in the application
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from functools import wraps
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class Permission(Enum):
    """
    Permission levels for access control.
    
    These represent the actions that can be performed on resources.
    Higher levels include lower level permissions.
    """
    NONE = 0
    READ = 1
    WRITE = 2
    DELETE = 3
    ADMIN = 4
    
    def __ge__(self, other):
        if isinstance(other, Permission):
            return self.value >= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if isinstance(other, Permission):
            return self.value > other.value
        return NotImplemented
    
    def __le__(self, other):
        if isinstance(other, Permission):
            return self.value <= other.value
        return NotImplemented
    
    def __lt__(self, other):
        if isinstance(other, Permission):
            return self.value < other.value
        return NotImplemented


class ResourceType(Enum):
    """
    Types of resources/objects in the system that require access control.
    """
    COMPANY = "company"
    VOUCHER = "voucher"
    INVOICE = "invoice"
    PRODUCT = "product"
    ORDER = "order"
    LEDGER = "ledger"
    REPORT = "report"
    USER = "user"
    PARTY = "party"
    STOCK = "stock"
    PAYMENT = "payment"
    SETTINGS = "settings"


@dataclass
class ACLEntry:
    """
    Single entry in the Access Control List.
    
    Attributes:
        subject: The user/role/group that this entry applies to
        resource_type: The type of resource being controlled
        resource_id: Optional specific resource ID (None means all resources of type)
        permission: The permission level granted
        conditions: Optional conditions for the permission
        justification: Why this access is granted (for audit)
    """
    subject: str
    resource_type: ResourceType
    permission: Permission
    resource_id: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    justification: str = ""
    
    def matches(self, subject: str, resource_type: ResourceType, 
                resource_id: Optional[str] = None) -> bool:
        """Check if this ACL entry matches the given request."""
        if self.subject != subject and self.subject != "*":
            return False
        if self.resource_type != resource_type:
            return False
        if self.resource_id and resource_id and self.resource_id != resource_id:
            return False
        return True


class AccessControlList:
    """
    Access Control List implementation.
    
    Maintains a list of ACL entries that define who can access what resources
    with what permissions. This is the object-centric view of access control.
    
    Example Usage:
        acl = AccessControlList()
        acl.grant("user:john", ResourceType.INVOICE, Permission.READ)
        acl.grant("role:ADMIN", ResourceType.INVOICE, Permission.ADMIN)
        
        if acl.check_permission("user:john", ResourceType.INVOICE, Permission.READ):
            # Allow access
    """
    
    def __init__(self):
        self._entries: List[ACLEntry] = []
        self._cache: Dict[Tuple[str, ResourceType, Optional[str]], Permission] = {}
    
    def grant(self, subject: str, resource_type: ResourceType, 
              permission: Permission, resource_id: Optional[str] = None,
              conditions: Optional[Dict] = None, justification: str = "") -> None:
        """
        Grant a permission to a subject for a resource.
        
        Args:
            subject: User/role identifier (e.g., "user:john", "role:ADMIN")
            resource_type: Type of resource
            permission: Permission level to grant
            resource_id: Optional specific resource ID
            conditions: Optional conditions for access
            justification: Reason for granting access
        """
        entry = ACLEntry(
            subject=subject,
            resource_type=resource_type,
            permission=permission,
            resource_id=resource_id,
            conditions=conditions or {},
            justification=justification
        )
        self._entries.append(entry)
        self._invalidate_cache()
        
        logger.info(
            f"ACL: Granted {permission.name} on {resource_type.value} "
            f"to {subject}. Justification: {justification}"
        )
    
    def revoke(self, subject: str, resource_type: ResourceType,
               resource_id: Optional[str] = None) -> bool:
        """
        Revoke all permissions for a subject on a resource.
        
        Returns True if any entries were removed.
        """
        original_count = len(self._entries)
        self._entries = [
            e for e in self._entries 
            if not e.matches(subject, resource_type, resource_id)
        ]
        removed = original_count - len(self._entries)
        
        if removed > 0:
            self._invalidate_cache()
            logger.info(
                f"ACL: Revoked {removed} entries for {subject} "
                f"on {resource_type.value}"
            )
        
        return removed > 0
    
    def check_permission(self, subject: str, resource_type: ResourceType,
                        required_permission: Permission,
                        resource_id: Optional[str] = None) -> bool:
        """
        Check if a subject has the required permission on a resource.
        
        Args:
            subject: User/role identifier
            resource_type: Type of resource
            required_permission: Minimum permission level required
            resource_id: Optional specific resource ID
            
        Returns:
            True if access is allowed, False otherwise
        """
        cache_key = (subject, resource_type, resource_id)
        
        if cache_key not in self._cache:
            # Find highest permission for this subject/resource
            max_permission = Permission.NONE
            for entry in self._entries:
                if entry.matches(subject, resource_type, resource_id):
                    if entry.permission > max_permission:
                        max_permission = entry.permission
            self._cache[cache_key] = max_permission
        
        return self._cache[cache_key] >= required_permission
    
    def get_permissions(self, subject: str) -> Dict[ResourceType, Permission]:
        """Get all permissions for a subject."""
        permissions = {}
        for entry in self._entries:
            if entry.subject == subject:
                if entry.resource_type not in permissions:
                    permissions[entry.resource_type] = entry.permission
                elif entry.permission > permissions[entry.resource_type]:
                    permissions[entry.resource_type] = entry.permission
        return permissions
    
    def list_entries(self, subject: Optional[str] = None,
                    resource_type: Optional[ResourceType] = None) -> List[ACLEntry]:
        """List ACL entries, optionally filtered."""
        entries = self._entries
        if subject:
            entries = [e for e in entries if e.subject == subject]
        if resource_type:
            entries = [e for e in entries if e.resource_type == resource_type]
        return entries
    
    def _invalidate_cache(self):
        """Clear the permission cache."""
        self._cache.clear()


class AccessControlMatrix:
    """
    Access Control Matrix implementation.
    
    Provides a matrix view of access control where:
    - Rows represent SUBJECTS (users, roles, groups)
    - Columns represent OBJECTS (resources)
    - Cells contain the PERMISSIONS
    
    This implementation includes at least 3 subjects and 3 objects as required:
    
    Subjects (Examples):
    1. OWNER - Company owner with full access
    2. ADMIN - Administrator with management access
    3. ACCOUNTANT - Financial operations access
    4. VIEWER - Read-only access
    
    Objects (Examples):
    1. INVOICE - Financial documents
    2. VOUCHER - Transaction records
    3. PRODUCT - Inventory items
    4. LEDGER - Account books
    
    Example Matrix:
                    | INVOICE | VOUCHER | PRODUCT | LEDGER |
    ----------------+---------+---------+---------+--------|
    OWNER           | ADMIN   | ADMIN   | ADMIN   | ADMIN  |
    ADMIN           | WRITE   | WRITE   | WRITE   | READ   |
    ACCOUNTANT      | WRITE   | WRITE   | READ    | WRITE  |
    VIEWER          | READ    | READ    | READ    | READ   |
    """
    
    # Default Access Control Matrix
    # This defines the base permissions for each role
    DEFAULT_MATRIX: Dict[str, Dict[ResourceType, Permission]] = {
        # Subject 1: OWNER - Full administrative access to everything
        "OWNER": {
            ResourceType.COMPANY: Permission.ADMIN,
            ResourceType.VOUCHER: Permission.ADMIN,
            ResourceType.INVOICE: Permission.ADMIN,
            ResourceType.PRODUCT: Permission.ADMIN,
            ResourceType.ORDER: Permission.ADMIN,
            ResourceType.LEDGER: Permission.ADMIN,
            ResourceType.REPORT: Permission.ADMIN,
            ResourceType.USER: Permission.ADMIN,
            ResourceType.PARTY: Permission.ADMIN,
            ResourceType.STOCK: Permission.ADMIN,
            ResourceType.PAYMENT: Permission.ADMIN,
            ResourceType.SETTINGS: Permission.ADMIN,
        },
        # Subject 2: ADMIN - Management access
        "ADMIN": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.WRITE,
            ResourceType.INVOICE: Permission.WRITE,
            ResourceType.PRODUCT: Permission.WRITE,
            ResourceType.ORDER: Permission.WRITE,
            ResourceType.LEDGER: Permission.READ,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.WRITE,
            ResourceType.PARTY: Permission.WRITE,
            ResourceType.STOCK: Permission.WRITE,
            ResourceType.PAYMENT: Permission.WRITE,
            ResourceType.SETTINGS: Permission.READ,
        },
        # Subject 3: ACCOUNTANT - Financial access
        "ACCOUNTANT": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.WRITE,
            ResourceType.INVOICE: Permission.WRITE,
            ResourceType.PRODUCT: Permission.READ,
            ResourceType.ORDER: Permission.READ,
            ResourceType.LEDGER: Permission.WRITE,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.NONE,
            ResourceType.PARTY: Permission.READ,
            ResourceType.STOCK: Permission.READ,
            ResourceType.PAYMENT: Permission.WRITE,
            ResourceType.SETTINGS: Permission.NONE,
        },
        # Subject 4: MANAGER - Operations management
        "MANAGER": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.READ,
            ResourceType.INVOICE: Permission.WRITE,
            ResourceType.PRODUCT: Permission.WRITE,
            ResourceType.ORDER: Permission.WRITE,
            ResourceType.LEDGER: Permission.READ,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.READ,
            ResourceType.PARTY: Permission.WRITE,
            ResourceType.STOCK: Permission.WRITE,
            ResourceType.PAYMENT: Permission.READ,
            ResourceType.SETTINGS: Permission.NONE,
        },
        # Subject 5: STOCK_KEEPER - Inventory access
        "STOCK_KEEPER": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.NONE,
            ResourceType.INVOICE: Permission.READ,
            ResourceType.PRODUCT: Permission.WRITE,
            ResourceType.ORDER: Permission.READ,
            ResourceType.LEDGER: Permission.NONE,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.NONE,
            ResourceType.PARTY: Permission.READ,
            ResourceType.STOCK: Permission.WRITE,
            ResourceType.PAYMENT: Permission.NONE,
            ResourceType.SETTINGS: Permission.NONE,
        },
        # Subject 6: SALES - Sales operations
        "SALES": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.READ,
            ResourceType.INVOICE: Permission.WRITE,
            ResourceType.PRODUCT: Permission.READ,
            ResourceType.ORDER: Permission.WRITE,
            ResourceType.LEDGER: Permission.NONE,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.NONE,
            ResourceType.PARTY: Permission.WRITE,
            ResourceType.STOCK: Permission.READ,
            ResourceType.PAYMENT: Permission.READ,
            ResourceType.SETTINGS: Permission.NONE,
        },
        # Subject 7: VIEWER - Read-only access
        "VIEWER": {
            ResourceType.COMPANY: Permission.READ,
            ResourceType.VOUCHER: Permission.READ,
            ResourceType.INVOICE: Permission.READ,
            ResourceType.PRODUCT: Permission.READ,
            ResourceType.ORDER: Permission.READ,
            ResourceType.LEDGER: Permission.READ,
            ResourceType.REPORT: Permission.READ,
            ResourceType.USER: Permission.NONE,
            ResourceType.PARTY: Permission.READ,
            ResourceType.STOCK: Permission.READ,
            ResourceType.PAYMENT: Permission.READ,
            ResourceType.SETTINGS: Permission.NONE,
        },
    }
    
    # Policy Justifications
    POLICY_JUSTIFICATIONS: Dict[str, str] = {
        "OWNER": "Company owner has full administrative rights to manage all aspects "
                 "of the business including users, financial data, and settings.",
        "ADMIN": "Administrators can manage day-to-day operations and users but cannot "
                 "modify company settings or access sensitive financial ledgers directly.",
        "ACCOUNTANT": "Accountants need write access to financial documents (vouchers, "
                      "invoices, payments, ledgers) but only read access to other areas.",
        "MANAGER": "Managers oversee operations, orders, and parties but have limited "
                   "financial access to maintain separation of duties.",
        "STOCK_KEEPER": "Stock keepers manage inventory but have no access to financial "
                        "data to prevent unauthorized modifications.",
        "SALES": "Sales team can create orders and invoices, manage parties, but cannot "
                 "access sensitive financial or user data.",
        "VIEWER": "Viewers have read-only access for reporting and monitoring purposes "
                  "without ability to modify any data.",
    }
    
    def __init__(self, company_id: Optional[str] = None):
        """
        Initialize Access Control Matrix.
        
        Args:
            company_id: Optional company context for multi-tenant systems
        """
        self.company_id = company_id
        self._matrix: Dict[str, Dict[ResourceType, Permission]] = dict(self.DEFAULT_MATRIX)
        self._custom_rules: List[ACLEntry] = []
    
    def get_permission(self, role: str, resource_type: ResourceType) -> Permission:
        """
        Get the permission level for a role on a resource type.
        
        Args:
            role: The role/subject
            resource_type: The resource/object type
            
        Returns:
            Permission level (NONE if not defined)
        """
        if role not in self._matrix:
            return Permission.NONE
        return self._matrix[role].get(resource_type, Permission.NONE)
    
    def check_access(self, role: str, resource_type: ResourceType,
                    required_permission: Permission) -> bool:
        """
        Check if a role has the required permission on a resource.
        
        Args:
            role: The role/subject
            resource_type: The resource/object type
            required_permission: Minimum permission required
            
        Returns:
            True if access is allowed
        """
        actual_permission = self.get_permission(role, resource_type)
        allowed = actual_permission >= required_permission
        
        logger.debug(
            f"ACM Check: {role} needs {required_permission.name} on "
            f"{resource_type.value}, has {actual_permission.name} -> "
            f"{'ALLOWED' if allowed else 'DENIED'}"
        )
        
        return allowed
    
    def set_permission(self, role: str, resource_type: ResourceType,
                      permission: Permission, justification: str = "") -> None:
        """
        Set or update a permission in the matrix.
        
        Args:
            role: The role/subject
            resource_type: The resource/object type
            permission: Permission level to set
            justification: Reason for the permission
        """
        if role not in self._matrix:
            self._matrix[role] = {}
        
        self._matrix[role][resource_type] = permission
        
        logger.info(
            f"ACM: Set {role} -> {resource_type.value} = {permission.name}. "
            f"Justification: {justification}"
        )
    
    def get_role_permissions(self, role: str) -> Dict[ResourceType, Permission]:
        """Get all permissions for a role."""
        return dict(self._matrix.get(role, {}))
    
    def get_resource_permissions(self, resource_type: ResourceType) -> Dict[str, Permission]:
        """Get all roles and their permissions for a resource type."""
        result = {}
        for role, permissions in self._matrix.items():
            if resource_type in permissions:
                result[role] = permissions[resource_type]
        return result
    
    def get_policy_justification(self, role: str) -> str:
        """Get the policy justification for a role."""
        return self.POLICY_JUSTIFICATIONS.get(role, "No justification provided.")
    
    def print_matrix(self) -> str:
        """
        Generate a string representation of the access control matrix.
        
        Returns formatted table showing all subjects and objects.
        """
        # Get all resource types that have any permissions
        resource_types = list(ResourceType)
        roles = list(self._matrix.keys())
        
        # Calculate column widths
        role_width = max(len(r) for r in roles) + 2
        perm_width = 8  # Width for permission names
        
        # Build header
        header = f"{'Role':<{role_width}}"
        for rt in resource_types:
            header += f" | {rt.value[:perm_width]:<{perm_width}}"
        
        separator = "-" * len(header)
        
        lines = [separator, header, separator]
        
        # Build rows
        for role in roles:
            row = f"{role:<{role_width}}"
            for rt in resource_types:
                perm = self._matrix.get(role, {}).get(rt, Permission.NONE)
                row += f" | {perm.name[:perm_width]:<{perm_width}}"
            lines.append(row)
        
        lines.append(separator)
        return "\n".join(lines)


def require_permission(resource_type: ResourceType, permission: Permission):
    """
    Decorator to enforce ACL-based access control on service functions.
    
    Usage:
        @require_permission(ResourceType.INVOICE, Permission.WRITE)
        def create_invoice(user, data):
            # Only users with WRITE permission on INVOICE can access this
            ...
    
    The decorated function must have 'user' as its first argument.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            from apps.company.models import CompanyUser
            
            # Get user's role
            company_user = CompanyUser.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if not company_user:
                raise PermissionDenied("No active company membership found.")
            
            # Check permission using ACM
            acm = AccessControlMatrix(company_id=str(company_user.company_id))
            
            if not acm.check_access(company_user.role, resource_type, permission):
                raise PermissionDenied(
                    f"Access denied: {permission.name} permission on "
                    f"{resource_type.value} is required. Your role: {company_user.role}"
                )
            
            return func(user, *args, **kwargs)
        return wrapper
    return decorator


# Global ACL instance for application-wide access control
_global_acl: Optional[AccessControlList] = None


def get_global_acl() -> AccessControlList:
    """Get the global ACL instance."""
    global _global_acl
    if _global_acl is None:
        _global_acl = AccessControlList()
        _setup_default_acl(_global_acl)
    return _global_acl


def _setup_default_acl(acl: AccessControlList) -> None:
    """Set up default ACL entries based on the Access Control Matrix."""
    acm = AccessControlMatrix()
    
    for role, permissions in acm._matrix.items():
        for resource_type, permission in permissions.items():
            acl.grant(
                subject=f"role:{role}",
                resource_type=resource_type,
                permission=permission,
                justification=acm.get_policy_justification(role)
            )
