"""
Custom exception classes for the application.
"""

from rest_framework.exceptions import APIException


class BusinessLogicError(APIException):
    """Base exception for business logic errors."""
    status_code = 400
    default_detail = 'A business logic error occurred.'
    default_code = 'business_logic_error'


class InsufficientInventoryError(BusinessLogicError):
    """Raised when there is insufficient inventory for an operation."""
    default_detail = 'Insufficient inventory available.'
    default_code = 'insufficient_inventory'


class InvalidOperationError(BusinessLogicError):
    """Raised when an invalid operation is attempted."""
    default_detail = 'Invalid operation.'
    default_code = 'invalid_operation'


class ResourceNotFoundError(APIException):
    """Raised when a requested resource is not found."""
    status_code = 404
    default_detail = 'Resource not found.'
    default_code = 'not_found'


class AlreadyPosted(BusinessLogicError):
    """Raised when attempting to modify an already posted transaction."""
    default_detail = 'Transaction has already been posted and cannot be modified.'
    default_code = 'already_posted'


class FinancialYearLockError(BusinessLogicError):
    """Raised when attempting to post/modify in a closed financial year."""
    default_detail = 'Financial year is closed. Cannot post or modify transactions.'
    default_code = 'financial_year_locked'


class CompanyLocked(BusinessLogicError):
    """Raised when attempting operations on a locked company."""
    default_detail = 'Company is locked. Cannot perform this operation.'
    default_code = 'company_locked'
