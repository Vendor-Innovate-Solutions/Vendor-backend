"""
GST API Views

Endpoints for generating and retrieving GST returns (GSTR-1, GSTR-3B).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.permissions.base import HasCompanyContext, RolePermission
from integrations.gst.services.returns_service import GSTReturnService
from integrations.gst.models import GSTR1, GSTR3B


class GSTR1GenerateView(APIView):
    """
    Generate GSTR-1 (outward supplies) for a tax period.
    
    POST /api/gst/gstr1/generate/
    
    Request:
    {
        "period": "2024-07"  // YYYY-MM format
    }
    
    Response:
    {
        "status": "GENERATED",
        "gstr1_id": "uuid",
        "period": "2024-07",
        "outward_taxable": "100000.00",
        "cgst": "9000.00",
        "sgst": "9000.00",
        "igst": "0.00",
        "total_tax": "18000.00"
    }
    
    Only ADMIN and ACCOUNTANT roles can generate GST returns.
    """
    permission_classes = [IsAuthenticated, HasCompanyContext, RolePermission.require(["ADMIN", "ACCOUNTANT"])]
    
    def post(self, request):
        """Generate GSTR-1 for the given period."""
        period = request.data.get("period")
        
        if not period:
            return Response(
                {"error": "period is required (format: YYYY-MM)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate period format
        try:
            year, month = period.split('-')
            if len(year) != 4 or len(month) != 2:
                raise ValueError
            int(year)
            int(month)
        except (ValueError, AttributeError):
            return Response(
                {"error": "Invalid period format. Use YYYY-MM (e.g., 2024-07)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            gstr1 = GSTReturnService.generate_gstr1(request.company, period)
            
            return Response(
                {
                    "status": "GENERATED",
                    "gstr1_id": str(gstr1.id),
                    "period": period,
                    "outward_taxable": str(gstr1.outward_taxable),
                    "cgst": str(gstr1.cgst),
                    "sgst": str(gstr1.sgst),
                    "igst": str(gstr1.igst),
                    "total_tax": str(gstr1.total_tax),
                    "created_at": gstr1.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to generate GSTR-1: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GSTR3BGenerateView(APIView):
    """
    Generate GSTR-3B (monthly return) for a tax period.
    
    POST /api/gst/gstr3b/generate/
    
    Request:
    {
        "period": "2024-07"  // YYYY-MM format
    }
    
    Response:
    {
        "status": "GENERATED",
        "gstr3b_id": "uuid",
        "period": "2024-07",
        "outward_taxable": "100000.00",
        "inward_itc_cgst": "5000.00",
        "inward_itc_sgst": "5000.00",
        "inward_itc_igst": "0.00",
        "cgst_payable": "4000.00",
        "sgst_payable": "4000.00",
        "igst_payable": "0.00",
        "total_payable": "8000.00"
    }
    
    Note: Automatically generates GSTR-1 if not already generated.
    Only ADMIN and ACCOUNTANT roles can generate GST returns.
    """
    permission_classes = [IsAuthenticated, HasCompanyContext, RolePermission.require(["ADMIN", "ACCOUNTANT"])]
    
    def post(self, request):
        """Generate GSTR-3B for the given period."""
        period = request.data.get("period")
        
        if not period:
            return Response(
                {"error": "period is required (format: YYYY-MM)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate period format
        try:
            year, month = period.split('-')
            if len(year) != 4 or len(month) != 2:
                raise ValueError
            int(year)
            int(month)
        except (ValueError, AttributeError):
            return Response(
                {"error": "Invalid period format. Use YYYY-MM (e.g., 2024-07)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            gstr3b = GSTReturnService.generate_gstr3b(request.company, period)
            
            return Response(
                {
                    "status": "GENERATED",
                    "gstr3b_id": str(gstr3b.id),
                    "period": period,
                    "outward_taxable": str(gstr3b.outward_taxable),
                    "inward_itc_cgst": str(gstr3b.inward_itc_cgst),
                    "inward_itc_sgst": str(gstr3b.inward_itc_sgst),
                    "inward_itc_igst": str(gstr3b.inward_itc_igst),
                    "cgst_payable": str(gstr3b.cgst_payable),
                    "sgst_payable": str(gstr3b.sgst_payable),
                    "igst_payable": str(gstr3b.igst_payable),
                    "total_payable": str(gstr3b.total_payable),
                    "created_at": gstr3b.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to generate GSTR-3B: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GSTReturnPeriodView(APIView):
    """
    Retrieve GST returns (GSTR-1 and GSTR-3B) for a specific period.
    
    GET /api/gst/returns/<period>/
    
    Example: GET /api/gst/returns/2024-07/
    
    Response:
    {
        "period": "2024-07",
        "company": "ABC Company Ltd",
        "gstr1": {
            "id": "uuid",
            "outward_taxable": "100000.00",
            "cgst": "9000.00",
            "sgst": "9000.00",
            "igst": "0.00",
            "total_tax": "18000.00",
            "created_at": "2024-08-01T10:00:00Z",
            "updated_at": "2024-08-01T10:00:00Z"
        },
        "gstr3b": {
            "id": "uuid",
            "outward_taxable": "100000.00",
            "inward_itc_cgst": "5000.00",
            "inward_itc_sgst": "5000.00",
            "inward_itc_igst": "0.00",
            "cgst_payable": "4000.00",
            "sgst_payable": "4000.00",
            "igst_payable": "0.00",
            "total_payable": "8000.00",
            "created_at": "2024-08-01T10:30:00Z",
            "updated_at": "2024-08-01T10:30:00Z"
        }
    }
    
    Returns null for gstr1/gstr3b if not yet generated.
    All authenticated users can view returns (company-scoped).
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def get(self, request, period):
        """Retrieve GST returns for the given period."""
        # Validate period format
        try:
            year, month = period.split('-')
            if len(year) != 4 or len(month) != 2:
                raise ValueError
            int(year)
            int(month)
        except (ValueError, AttributeError):
            return Response(
                {"error": "Invalid period format. Use YYYY-MM (e.g., 2024-07)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = GSTReturnService.get_period_returns(request.company, period)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve GST returns: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GSTReturnListView(APIView):
    """
    List all GST returns for the company.
    
    GET /api/gst/returns/
    
    Optional query parameters:
    - year: Filter by year (e.g., 2024)
    - type: Filter by return type ('gstr1' or 'gstr3b')
    
    Response:
    {
        "gstr1_returns": [
            {
                "id": "uuid",
                "period": "2024-07",
                "outward_taxable": "100000.00",
                "total_tax": "18000.00",
                "created_at": "2024-08-01T10:00:00Z"
            }
        ],
        "gstr3b_returns": [
            {
                "id": "uuid",
                "period": "2024-07",
                "total_payable": "8000.00",
                "created_at": "2024-08-01T10:30:00Z"
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def get(self, request):
        """List all GST returns for the company."""
        year = request.query_params.get('year')
        return_type = request.query_params.get('type')
        
        result = {
            'gstr1_returns': [],
            'gstr3b_returns': []
        }
        
        # Filter GSTR-1
        if not return_type or return_type == 'gstr1':
            gstr1_qs = GSTR1.objects.filter(company=request.company)
            if year:
                gstr1_qs = gstr1_qs.filter(period__startswith=year)
            
            result['gstr1_returns'] = [
                {
                    'id': str(g.id),
                    'period': g.period,
                    'outward_taxable': str(g.outward_taxable),
                    'cgst': str(g.cgst),
                    'sgst': str(g.sgst),
                    'igst': str(g.igst),
                    'total_tax': str(g.total_tax),
                    'created_at': g.created_at.isoformat(),
                }
                for g in gstr1_qs.order_by('-period')
            ]
        
        # Filter GSTR-3B
        if not return_type or return_type == 'gstr3b':
            gstr3b_qs = GSTR3B.objects.filter(company=request.company)
            if year:
                gstr3b_qs = gstr3b_qs.filter(period__startswith=year)
            
            result['gstr3b_returns'] = [
                {
                    'id': str(g.id),
                    'period': g.period,
                    'outward_taxable': str(g.outward_taxable),
                    'cgst_payable': str(g.cgst_payable),
                    'sgst_payable': str(g.sgst_payable),
                    'igst_payable': str(g.igst_payable),
                    'total_payable': str(g.total_payable),
                    'created_at': g.created_at.isoformat(),
                }
                for g in gstr3b_qs.order_by('-period')
            ]
        
        return Response(result, status=status.HTTP_200_OK)
