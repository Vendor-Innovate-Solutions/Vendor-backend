"""
Reporting API Views.

Exposes aging reports and other financial reports via REST API.

PHASE 5 - Aging Report APIs:
- GET /api/reports/aging/ - Full aging report with party breakdown
- GET /api/reports/aging/summary/ - Quick summary (buckets only)
- GET /api/reports/overdue/ - List of overdue parties

All endpoints respect company isolation and require authentication.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from datetime import date, datetime
from typing import Optional


class AgingReportView(APIView):
    """
    GET full aging report with party-wise breakdown.
    
    Endpoint: GET /api/reports/aging/
    
    Query Params:
        as_of_date: Date for calculation (YYYY-MM-DD) - default: today
        use_cache: Whether to use cached report (true/false) - default: true
        
    Response:
        {
            "company_id": "...",
            "company_name": "...",
            "total_outstanding": "150000.00",
            "buckets": {
                "0-30": "50000.00",
                "31-60": "40000.00",
                "61-90": "30000.00",
                "90+": "30000.00"
            },
            "parties": [
                {
                    "party_id": "...",
                    "party_name": "ABC Retailers",
                    "total": "50000.00",
                    "buckets": {...},
                    "invoices": [...]
                }
            ],
            "as_of_date": "2024-01-15",
            "generated_at": "2024-01-15T10:30:00Z"
        }
    
    Permissions:
        - Authenticated users only
        - Company scoped (uses request.company)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        company = request.company
        
        # Parse as_of_date from query params
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            as_of_date = None  # Will use today
        
        # Check if should use cache
        use_cache = request.query_params.get('use_cache', 'true').lower() == 'true'
        
        from apps.reporting.services.aging import (
            aging_for_company,
            get_cached_aging,
            generate_and_cache_aging
        )
        
        if use_cache:
            # Try to get cached report
            report = get_cached_aging(company, as_of_date)
            
            if not report:
                # No cache, generate and cache
                report = generate_and_cache_aging(company, as_of_date)
        else:
            # Generate fresh report (don't use cache)
            report = aging_for_company(company, as_of_date)
        
        return Response(report, status=status.HTTP_200_OK)


class AgingSummaryView(APIView):
    """
    GET quick aging summary (buckets only, no party details).
    
    Endpoint: GET /api/reports/aging/summary/
    
    Query Params:
        as_of_date: Date for calculation (YYYY-MM-DD) - default: today
        
    Response:
        {
            "company_id": "...",
            "total_outstanding": "150000.00",
            "buckets": {
                "0-30": "50000.00",
                "31-60": "40000.00",
                "61-90": "30000.00",
                "90+": "30000.00"
            },
            "as_of_date": "2024-01-15"
        }
    
    Permissions:
        - Authenticated users only
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        company = request.company
        
        # Parse as_of_date
        as_of_date_str = request.query_params.get('as_of_date')
        if as_of_date_str:
            try:
                as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Invalid date format. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            as_of_date = None
        
        from apps.reporting.services.aging import aging_summary
        
        summary = aging_summary(company, as_of_date)
        return Response(summary, status=status.HTTP_200_OK)


class OverduePartiesView(APIView):
    """
    GET list of parties with overdue amounts.
    
    Endpoint: GET /api/reports/overdue/
    
    Query Params:
        days_threshold: Minimum days overdue (default: 30)
        
    Response:
        [
            {
                "party_id": "...",
                "party_name": "ABC Retailers",
                "overdue_amount": "50000.00",
                "oldest_invoice_days": 75,
                "invoice_count": 3
            }
        ]
    
    Permissions:
        - Authenticated users only
        - Useful for collections team
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        company = request.company
        
        # Parse days_threshold
        days_threshold = int(request.query_params.get('days_threshold', 30))
        
        if days_threshold < 0:
            return Response(
                {"error": "days_threshold must be >= 0"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.reporting.services.aging import overdue_parties
        
        parties = overdue_parties(company, days_threshold)
        return Response(parties, status=status.HTTP_200_OK)
