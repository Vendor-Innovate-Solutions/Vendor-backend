"""
Accounting API views.
"""
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.decorators import action
from core.drf.viewsets import CompanyScopedViewSet
from core.drf.permissions import HasCompanyContext, RolePermission
from apps.accounting.models import Ledger, AccountGroup
from apps.company.models import FinancialYear
from apps.accounting.api.serializers import (
    LedgerSerializer, LedgerDetailSerializer,
    AccountGroupSerializer, FinancialYearSerializer
)
from apps.accounting.selectors import ledger_balance_detailed
from apps.reporting.services.financial_reports import (
    trial_balance, profit_and_loss, balance_sheet, ledger_statement
)


class LedgerViewSet(CompanyScopedViewSet):
    """
    ViewSet for Ledger CRUD operations.
    
    Automatically filtered by request.company.
    """
    queryset = Ledger.objects.all().select_related('group')
    serializer_class = LedgerSerializer
    permission_classes = [HasCompanyContext]
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action."""
        if self.action == 'retrieve':
            return LedgerDetailSerializer
        return LedgerSerializer
    
    @action(detail=True, methods=['get'], url_path='balance')
    def balance(self, request, pk=None):
        """
        Get balance for a specific ledger.
        
        GET /api/accounting/ledgers/{id}/balance/
        ?financial_year_id=<fy_id>
        """
        ledger = self.get_object()
        fy_id = request.query_params.get('financial_year_id')
        
        if not fy_id:
            # Use current/active financial year
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    is_closed=False
                )
                fy_id = fy.id
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'No active financial year found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        balance_data = ledger_balance_detailed(request.company, ledger, fy_id)
        return Response(balance_data)
    
    @action(detail=True, methods=['get'], url_path='statement')
    def statement(self, request, pk=None):
        """
        Get ledger statement (transaction history).
        
        GET /api/accounting/ledgers/{id}/statement/
        ?financial_year_id=<fy_id>&start_date=2024-01-01&end_date=2024-12-31
        """
        ledger = self.get_object()
        fy_id = request.query_params.get('financial_year_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not fy_id:
            # Use current financial year
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    is_closed=False
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'No active financial year found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    id=fy_id
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'Financial year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        statement_data = ledger_statement(
            request.company,
            ledger.id,
            fy,
            start_date,
            end_date
        )
        return Response(statement_data)


class AccountGroupViewSet(CompanyScopedViewSet):
    """
    ViewSet for AccountGroup CRUD operations.
    
    Automatically filtered by request.company.
    """
    queryset = AccountGroup.objects.all().select_related('parent')
    serializer_class = AccountGroupSerializer
    permission_classes = [HasCompanyContext]


class FinancialYearViewSet(CompanyScopedViewSet):
    """
    ViewSet for FinancialYear CRUD operations.
    
    Automatically filtered by request.company.
    """
    queryset = FinancialYear.objects.all()
    serializer_class = FinancialYearSerializer
    permission_classes = [HasCompanyContext]
    
    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """
        Get current/active financial year.
        
        GET /api/accounting/financial-years/current/
        """
        try:
            fy = FinancialYear.objects.get(
                company=request.company,
                is_closed=False
            )
            serializer = self.get_serializer(fy)
            return Response(serializer.data)
        except FinancialYear.DoesNotExist:
            return Response(
                {'error': 'No active financial year found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TrialBalanceView(APIView):
    """
    Trial Balance report endpoint.
    
    GET /api/accounting/reports/trial-balance/
    ?financial_year_id=<fy_id>
    """
    permission_classes = [HasCompanyContext]
    
    def get(self, request):
        fy_id = request.query_params.get('financial_year_id')
        
        if fy_id:
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    id=fy_id
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'Financial year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use current financial year
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    is_closed=False
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'No active financial year found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        data = trial_balance(request.company, fy)
        return Response(data)


class ProfitLossView(APIView):
    """
    Profit & Loss Statement endpoint.
    
    GET /api/accounting/reports/pl/
    ?financial_year_id=<fy_id>
    """
    permission_classes = [HasCompanyContext, RolePermission.require(['ADMIN', 'ACCOUNTANT', 'MANAGER'])]
    
    def get(self, request):
        fy_id = request.query_params.get('financial_year_id')
        
        if fy_id:
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    id=fy_id
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'Financial year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use current financial year
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    is_closed=False
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'No active financial year found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        data = profit_and_loss(request.company, fy)
        return Response(data)


class BalanceSheetView(APIView):
    """
    Balance Sheet report endpoint.
    
    GET /api/accounting/reports/bs/
    ?financial_year_id=<fy_id>
    """
    permission_classes = [HasCompanyContext, RolePermission.require(['ADMIN', 'ACCOUNTANT', 'MANAGER'])]
    
    def get(self, request):
        fy_id = request.query_params.get('financial_year_id')
        
        if fy_id:
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    id=fy_id
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'Financial year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use current financial year
            try:
                fy = FinancialYear.objects.get(
                    company=request.company,
                    is_closed=False
                )
            except FinancialYear.DoesNotExist:
                return Response(
                    {'error': 'No active financial year found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        data = balance_sheet(request.company, fy)
        return Response(data)
