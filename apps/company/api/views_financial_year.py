"""
Financial Year Management API Views

Endpoints for closing and reopening financial years for compliance.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.permissions.base import HasCompanyContext, RolePermission
from apps.company.models import FinancialYear


class FinancialYearCloseView(APIView):
    """
    Close a financial year.
    
    POST /api/company/financial_year/<uuid:fy_id>/close/
    
    Closing a financial year prevents:
    - New voucher posting
    - Voucher reversal
    - Any transaction modifications
    
    This is critical for:
    - Audit compliance
    - GST compliance
    - Financial integrity
    - Statutory reporting
    
    Only ADMIN and ACCOUNTANT roles can close financial years.
    Once closed, transactions cannot be posted to this FY.
    
    Response:
    {
        "status": "CLOSED",
        "financial_year": {
            "id": "uuid",
            "name": "FY 2023-24",
            "start_date": "2023-04-01",
            "end_date": "2024-03-31",
            "is_closed": true,
            "is_current": false
        },
        "message": "Financial year FY 2023-24 has been closed"
    }
    """
    permission_classes = [
        IsAuthenticated,
        HasCompanyContext,
        RolePermission.require(["ADMIN", "ACCOUNTANT"])
    ]
    
    def post(self, request, fy_id):
        """Close the specified financial year."""
        # Get FY for the company
        fy = get_object_or_404(
            FinancialYear,
            id=fy_id,
            company=request.company
        )
        
        # Check if already closed
        if fy.is_closed:
            return Response(
                {
                    "error": "Financial year is already closed",
                    "financial_year": {
                        "id": str(fy.id),
                        "name": fy.name,
                        "is_closed": True
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cannot close current financial year without confirmation
        if fy.is_current:
            return Response(
                {
                    "error": "Cannot close the current financial year. Please set another FY as current first.",
                    "financial_year": {
                        "id": str(fy.id),
                        "name": fy.name,
                        "is_current": True
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Close the financial year
        fy.is_closed = True
        fy.save(update_fields=["is_closed", "updated_at"])
        
        # Log the closure
        from apps.system.models import AuditLog
        AuditLog.objects.create(
            company=request.company,
            user=request.user,
            action="FY_CLOSED",
            entity_type="FinancialYear",
            entity_id=fy.id,
            description=f"Financial year {fy.name} closed by {request.user.username}"
        )
        
        return Response(
            {
                "status": "CLOSED",
                "financial_year": {
                    "id": str(fy.id),
                    "name": fy.name,
                    "start_date": fy.start_date.isoformat(),
                    "end_date": fy.end_date.isoformat(),
                    "is_closed": True,
                    "is_current": fy.is_current
                },
                "message": f"Financial year {fy.name} has been closed"
            },
            status=status.HTTP_200_OK
        )


class FinancialYearReopenView(APIView):
    """
    Reopen a closed financial year.
    
    POST /api/company/financial_year/<uuid:fy_id>/reopen/
    
    Reopening allows posting and reversal again.
    
    ⚠️ CRITICAL: Only ADMIN can reopen financial years.
    This is a sensitive operation that should only be done:
    - For error correction
    - With proper authorization
    - After considering audit implications
    
    Response:
    {
        "status": "REOPENED",
        "financial_year": {
            "id": "uuid",
            "name": "FY 2023-24",
            "start_date": "2023-04-01",
            "end_date": "2024-03-31",
            "is_closed": false,
            "is_current": false
        },
        "message": "Financial year FY 2023-24 has been reopened",
        "warning": "This action allows modifications to closed period. Ensure proper authorization."
    }
    """
    permission_classes = [
        IsAuthenticated,
        HasCompanyContext,
        RolePermission.require(["ADMIN"])  # Only ADMIN can reopen
    ]
    
    def post(self, request, fy_id):
        """Reopen the specified financial year."""
        # Get FY for the company
        fy = get_object_or_404(
            FinancialYear,
            id=fy_id,
            company=request.company
        )
        
        # Check if already open
        if not fy.is_closed:
            return Response(
                {
                    "error": "Financial year is already open",
                    "financial_year": {
                        "id": str(fy.id),
                        "name": fy.name,
                        "is_closed": False
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reopen the financial year
        fy.is_closed = False
        fy.save(update_fields=["is_closed", "updated_at"])
        
        # Log the reopening (critical audit event)
        from apps.system.models import AuditLog
        AuditLog.objects.create(
            company=request.company,
            user=request.user,
            action="FY_REOPENED",
            entity_type="FinancialYear",
            entity_id=fy.id,
            description=f"Financial year {fy.name} reopened by ADMIN {request.user.username}",
            severity="HIGH"  # Mark as high severity for audit trail
        )
        
        return Response(
            {
                "status": "REOPENED",
                "financial_year": {
                    "id": str(fy.id),
                    "name": fy.name,
                    "start_date": fy.start_date.isoformat(),
                    "end_date": fy.end_date.isoformat(),
                    "is_closed": False,
                    "is_current": fy.is_current
                },
                "message": f"Financial year {fy.name} has been reopened",
                "warning": "This action allows modifications to closed period. Ensure proper authorization."
            },
            status=status.HTTP_200_OK
        )


class FinancialYearListView(APIView):
    """
    List all financial years for the company.
    
    GET /api/company/financial_year/
    
    Response:
    {
        "financial_years": [
            {
                "id": "uuid",
                "name": "FY 2023-24",
                "start_date": "2023-04-01",
                "end_date": "2024-03-31",
                "is_current": true,
                "is_closed": false
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def get(self, request):
        """List all financial years."""
        fys = FinancialYear.objects.filter(
            company=request.company
        ).order_by('-start_date')
        
        return Response(
            {
                "financial_years": [
                    {
                        "id": str(fy.id),
                        "name": fy.name,
                        "start_date": fy.start_date.isoformat(),
                        "end_date": fy.end_date.isoformat(),
                        "is_current": fy.is_current,
                        "is_closed": fy.is_closed
                    }
                    for fy in fys
                ]
            },
            status=status.HTTP_200_OK
        )
