"""
Unified DRF exception handler for consistent API error responses.

All API errors return the format:
{
    "error": true,
    "message": "Human-readable error message",
    "code": "ERROR_CODE",
    "details": {...}  // Optional field-level errors
}
"""
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.db import IntegrityError


def unified_exception_handler(exc, context):
    """
    Custom exception handler for DRF that standardizes all error responses.
    
    Args:
        exc: The exception instance
        context: Dictionary with 'view' and 'request' keys
    
    Returns:
        Response object with standardized error format
    """
    # Call DRF's default handler first to get the standard error response
    response = drf_exception_handler(exc, context)
    
    # If DRF handled it, transform to our format
    if response is not None:
        error_data = {
            "error": True,
            "message": _extract_error_message(response.data),
            "code": _get_error_code(exc),
        }
        
        # Add field-level details for validation errors
        if isinstance(exc, ValidationError) and isinstance(response.data, dict):
            error_data["details"] = response.data
        
        response.data = error_data
        return response
    
    # Handle Django exceptions not caught by DRF
    if isinstance(exc, DjangoValidationError):
        return Response({
            "error": True,
            "message": _extract_django_validation_message(exc),
            "code": "VALIDATION_ERROR",
        }, status=400)
    
    if isinstance(exc, Http404):
        return Response({
            "error": True,
            "message": "Resource not found",
            "code": "NOT_FOUND",
        }, status=404)
    
    if isinstance(exc, IntegrityError):
        return Response({
            "error": True,
            "message": "Database integrity error. Possible duplicate or foreign key violation.",
            "code": "INTEGRITY_ERROR",
        }, status=400)
    
    # For any other unhandled exception, return generic 500 error
    return Response({
        "error": True,
        "message": "An unexpected error occurred",
        "code": "INTERNAL_ERROR",
    }, status=500)


def _extract_error_message(data):
    """
    Extract a single error message from DRF error data.
    
    Args:
        data: DRF error data (could be string, list, or dict)
    
    Returns:
        String error message
    """
    if isinstance(data, str):
        return data
    
    if isinstance(data, list) and len(data) > 0:
        return str(data[0])
    
    if isinstance(data, dict):
        # For validation errors, try to get the first error
        if 'detail' in data:
            return _extract_error_message(data['detail'])
        
        # Get first field error
        for field, errors in data.items():
            if isinstance(errors, list) and len(errors) > 0:
                return f"{field}: {errors[0]}"
            return f"{field}: {errors}"
    
    return "An error occurred"


def _extract_django_validation_message(exc):
    """
    Extract message from Django ValidationError.
    
    Args:
        exc: Django ValidationError instance
    
    Returns:
        String error message
    """
    if hasattr(exc, 'message_dict'):
        # Field-level validation errors
        messages = []
        for field, errors in exc.message_dict.items():
            messages.append(f"{field}: {', '.join(errors)}")
        return '; '.join(messages)
    
    if hasattr(exc, 'messages'):
        return '; '.join(exc.messages)
    
    return str(exc)


def _get_error_code(exc):
    """
    Extract or generate error code from exception.
    
    Args:
        exc: Exception instance
    
    Returns:
        String error code
    """
    # Check if exception has a custom code
    if hasattr(exc, 'default_code'):
        return exc.default_code.upper()
    
    # Use exception class name as code
    return exc.__class__.__name__.replace('Error', '').upper()


# Custom API exceptions for common business logic errors

class CompanyMismatchError(APIException):
    """Raised when attempting to access resources from a different company."""
    status_code = 403
    default_detail = "You do not have permission to access resources from this company"
    default_code = "COMPANY_MISMATCH"


class InvalidVoucherStateError(APIException):
    """Raised when a voucher operation is invalid for the current state."""
    status_code = 400
    default_detail = "Invalid voucher state for this operation"
    default_code = "INVALID_VOUCHER_STATE"


class AlreadyReversedError(APIException):
    """Raised when attempting to reverse an already-reversed voucher."""
    status_code = 400
    default_detail = "This voucher has already been reversed"
    default_code = "ALREADY_REVERSED"


class ClosedFinancialYearError(APIException):
    """Raised when attempting to modify a closed financial year."""
    status_code = 400
    default_detail = "Cannot modify records in a closed financial year"
    default_code = "CLOSED_FINANCIAL_YEAR"


class InsufficientStockError(APIException):
    """Raised when stock quantity is insufficient for the operation."""
    status_code = 400
    default_detail = "Insufficient stock quantity"
    default_code = "INSUFFICIENT_STOCK"


class InvalidPostingError(APIException):
    """Raised when accounting posting validation fails."""
    status_code = 400
    default_detail = "Invalid accounting posting"
    default_code = "INVALID_POSTING"
