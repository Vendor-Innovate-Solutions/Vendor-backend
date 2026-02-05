"""
Workflow API Views

Endpoints for approval management (maker-checker-poster pattern) and employee allocation.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

from core.permissions.base import HasCompanyContext, RolePermission
from apps.workflow.models import Approval, ApprovalStatus


class AvailableEmployeesView(APIView):
    """
    Get list of available employees for order allocation.
    
    GET /api/workflow/employees/available/
    
    Query params:
    - order_id (optional): Order ID to check availability against
    
    Response:
    {
        "employees": [
            {
                "id": "uuid",
                "employee_code": "EMP001",
                "name": "John Doe",
                "designation": "Delivery Manager",
                "department": "Logistics"
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get available employees."""
        from apps.hr.models import Employee
        
        company = request.company
        order_id = request.query_params.get('order_id')
        
        # Get all active employees for the company
        employees = Employee.objects.filter(
            company=company,
            is_active=True
        ).select_related('department')
        
        employee_list = [{
            'id': str(emp.id),
            'employee_code': emp.employee_code,
            'name': emp.name,
            'designation': emp.designation,
            'department': emp.department.name if emp.department else None
        } for emp in employees]
        
        return Response({
            'employees': employee_list
        })


class AssignOrderToEmployeeView(APIView):
    """
    Assign an order to an employee for processing/delivery.
    
    POST /api/workflow/orders/{order_id}/assign/
    
    Request:
    {
        "employee_id": "uuid"
    }
    
    Response:
    {
        "message": "Order assigned successfully",
        "order_id": "uuid",
        "employee_id": "uuid"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, order_id):
        """Assign order to employee."""
        from apps.orders.models import SalesOrder
        from apps.hr.models import Employee
        
        company = request.company
        employee_id = request.data.get('employee_id')
        
        if not employee_id:
            return Response(
                {'error': 'employee_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get order
            order = SalesOrder.objects.get(company=company, id=order_id)
            
            # Get employee
            employee = Employee.objects.get(company=company, id=employee_id, is_active=True)
            
            # Assign employee to order
            order.assigned_employee = employee
            order.save(update_fields=['assigned_employee', 'updated_at'])
            
            return Response({
                'message': 'Order assigned successfully',
                'order_id': str(order_id),
                'employee_id': str(employee_id),
                'employee_name': employee.name
            })
            
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Employee.DoesNotExist:
            return Response(
                {'error': 'Employee not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ApprovalRequestView(APIView):
    """
    Submit an object for approval.
    
    POST /api/workflow/request/
    
    Request:
    {
        "target_type": "voucher",
        "target_id": "uuid",
        "remarks": "Please approve this voucher"
    }
    
    Response:
    {
        "status": "SUBMITTED",
        "approval_id": "uuid",
        "message": "Approval request created successfully"
    }
    
    Permissions: All authenticated users (makers)
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def post(self, request):
        """Submit approval request."""
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')
        remarks = request.data.get('remarks', '')
        
        if not target_type or not target_id:
            return Response(
                {"error": "target_type and target_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already exists
        existing = Approval.objects.filter(
            company=request.company,
            target_type=target_type,
            target_id=target_id,
            status=ApprovalStatus.PENDING
        ).first()
        
        if existing:
            return Response(
                {
                    "error": "Approval request already exists",
                    "approval_id": str(existing.id)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create approval request
        approval = Approval.objects.create(
            company=request.company,
            target_type=target_type,
            target_id=target_id,
            requested_by=request.user,
            remarks=remarks,
            status=ApprovalStatus.PENDING
        )
        
        return Response(
            {
                "status": "SUBMITTED",
                "approval_id": str(approval.id),
                "message": "Approval request created successfully"
            },
            status=status.HTTP_201_CREATED
        )


class ApprovalApproveView(APIView):
    """
    Approve a pending request.
    
    POST /api/workflow/approve/<target_type>/<target_id>/
    
    Request:
    {
        "remarks": "Approved after document verification"
    }
    
    Response:
    {
        "status": "APPROVED",
        "approval_id": "uuid",
        "approved_by": "checker_username",
        "approved_at": "2024-12-26T10:30:00Z"
    }
    
    Permissions: ADMIN, ACCOUNTANT (checkers)
    """
    permission_classes = [
        IsAuthenticated,
        HasCompanyContext,
        RolePermission.require(["ADMIN", "ACCOUNTANT"])
    ]
    
    def post(self, request, target_type, target_id):
        """Approve request."""
        remarks = request.data.get('remarks', '')
        
        # Get pending approval
        approval = get_object_or_404(
            Approval,
            company=request.company,
            target_type=target_type,
            target_id=target_id,
            status=ApprovalStatus.PENDING
        )
        
        # Cannot approve own request
        if approval.requested_by == request.user:
            return Response(
                {"error": "Cannot approve your own request"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            approval.approve(request.user, remarks)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                "status": "APPROVED",
                "approval_id": str(approval.id),
                "approved_by": request.user.username,
                "approved_at": approval.approved_at.isoformat()
            },
            status=status.HTTP_200_OK
        )


class ApprovalRejectView(APIView):
    """
    Reject a pending request.
    
    POST /api/workflow/reject/<target_type>/<target_id>/
    
    Request:
    {
        "remarks": "Missing supporting documents"
    }
    
    Response:
    {
        "status": "REJECTED",
        "approval_id": "uuid",
        "rejected_by": "checker_username",
        "rejected_at": "2024-12-26T10:30:00Z",
        "reason": "Missing supporting documents"
    }
    
    Permissions: ADMIN, ACCOUNTANT (checkers)
    """
    permission_classes = [
        IsAuthenticated,
        HasCompanyContext,
        RolePermission.require(["ADMIN", "ACCOUNTANT"])
    ]
    
    def post(self, request, target_type, target_id):
        """Reject request."""
        remarks = request.data.get('remarks')
        
        if not remarks:
            return Response(
                {"error": "Rejection reason (remarks) is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get pending approval
        approval = get_object_or_404(
            Approval,
            company=request.company,
            target_type=target_type,
            target_id=target_id,
            status=ApprovalStatus.PENDING
        )
        
        try:
            approval.reject(request.user, remarks)
        except DjangoValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                "status": "REJECTED",
                "approval_id": str(approval.id),
                "rejected_by": request.user.username,
                "rejected_at": approval.approved_at.isoformat(),
                "reason": remarks
            },
            status=status.HTTP_200_OK
        )


class ApprovalListView(APIView):
    """
    List approval requests.
    
    GET /api/workflow/approvals/
    
    Optional query parameters:
    - status: Filter by status (PENDING, APPROVED, REJECTED)
    - target_type: Filter by type (voucher, order)
    - requested_by_me: true to see only my requests
    
    Response:
    {
        "approvals": [
            {
                "id": "uuid",
                "target_type": "voucher",
                "target_id": "uuid",
                "status": "PENDING",
                "requested_by": "maker_username",
                "approved_by": null,
                "remarks": "",
                "created_at": "2024-12-26T09:00:00Z"
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def get(self, request):
        """List approvals."""
        qs = Approval.objects.filter(company=request.company)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        target_type = request.query_params.get('target_type')
        if target_type:
            qs = qs.filter(target_type=target_type)
        
        requested_by_me = request.query_params.get('requested_by_me')
        if requested_by_me == 'true':
            qs = qs.filter(requested_by=request.user)
        
        approvals = [
            {
                'id': str(a.id),
                'target_type': a.target_type,
                'target_id': str(a.target_id),
                'status': a.status,
                'requested_by': a.requested_by.username,
                'approved_by': a.approved_by.username if a.approved_by else None,
                'remarks': a.remarks,
                'created_at': a.created_at.isoformat(),
                'approved_at': a.approved_at.isoformat() if a.approved_at else None
            }
            for a in qs.order_by('-created_at')
        ]
        
        return Response({'approvals': approvals}, status=status.HTTP_200_OK)


class ApprovalStatusView(APIView):
    """
    Check approval status for a specific object.
    
    GET /api/workflow/status/<target_type>/<target_id>/
    
    Response:
    {
        "has_approval": true,
        "status": "APPROVED",
        "approval_id": "uuid",
        "approved_by": "checker_username",
        "approved_at": "2024-12-26T10:30:00Z"
    }
    
    OR
    
    {
        "has_approval": false,
        "message": "No approval request found"
    }
    """
    permission_classes = [IsAuthenticated, HasCompanyContext]
    
    def get(self, request, target_type, target_id):
        """Check approval status."""
        approval = Approval.objects.filter(
            company=request.company,
            target_type=target_type,
            target_id=target_id
        ).order_by('-created_at').first()
        
        if not approval:
            return Response(
                {
                    "has_approval": False,
                    "message": "No approval request found"
                },
                status=status.HTTP_200_OK
            )
        
        return Response(
            {
                "has_approval": True,
                "status": approval.status,
                "approval_id": str(approval.id),
                "requested_by": approval.requested_by.username,
                "approved_by": approval.approved_by.username if approval.approved_by else None,
                "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
                "remarks": approval.remarks
            },
            status=status.HTTP_200_OK
        )
