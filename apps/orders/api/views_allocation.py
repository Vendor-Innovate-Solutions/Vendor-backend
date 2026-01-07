"""
Order allocation APIs for assigning delivery employees to orders.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count
from django.utils import timezone

from core.permissions.base import RolePermission
from apps.orders.models import SalesOrder
from apps.hr.models import Employee
from apps.users.models import Employee as UserEmployee


class GetAvailableEmployeesView(APIView):
    """
    Get list of employees available for order allocation/delivery.
    
    GET: List available employees for a specific order
    Requires: ADMIN, MANAGER, or SALES role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'MANAGER', 'SALES'])]
    
    def get(self, request):
        """
        Get available employees for order allocation.
        
        Query Params:
            order_id: Order UUID (optional, for context)
        """
        company = request.company
        order_id = request.query_params.get('order_id')
        
        # Verify order exists if order_id provided
        if order_id:
            try:
                order = SalesOrder.objects.get(id=order_id, company=company)
            except SalesOrder.DoesNotExist:
                return Response(
                    {'error': 'Order not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get active HR employees from company
        hr_employees = Employee.objects.filter(
            company=company,
            is_active=True
        ).select_related('user', 'department').order_by('first_name', 'last_name')
        
        # Build employee list
        employees = []
        for emp in hr_employees:
            employee_data = {
                'id': str(emp.id),
                'employee_code': emp.employee_code,
                'name': emp.name,
                'first_name': emp.first_name,
                'last_name': emp.last_name,
                'designation': emp.designation,
                'department': {
                    'code': emp.department.code,
                    'name': emp.department.name
                } if emp.department else None,
                'phone': emp.phone,
                'email': emp.email,
                'has_user_access': bool(emp.user_id)
            }
            employees.append(employee_data)
        
        # Also include users.Employee (lightweight identity model)
        user_employees = UserEmployee.objects.filter(
            company=company,
            is_active=True
        ).select_related('user').exclude(
            # Exclude if already in hr.Employee list
            user__employee_profiles__company=company
        )
        
        for emp in user_employees:
            if emp.user:
                employee_data = {
                    'id': f"user_{emp.employee_id}",
                    'employee_code': f"USR{emp.employee_id:04d}",
                    'name': emp.user.get_full_name() or emp.user.username,
                    'first_name': emp.user.first_name,
                    'last_name': emp.user.last_name,
                    'designation': emp.designation or 'Staff',
                    'department': {
                        'code': emp.department or 'GEN',
                        'name': emp.department or 'General'
                    } if emp.department else None,
                    'phone': emp.contact,
                    'email': emp.user.email,
                    'has_user_access': True
                }
                employees.append(employee_data)
        
        return Response({
            'employees': employees,
            'count': len(employees)
        })


class AllocateOrderView(APIView):
    """
    Allocate/assign order to delivery employee.
    
    POST: Assign order to employee
    Requires: ADMIN, MANAGER, or SALES role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'MANAGER', 'SALES'])]
    
    def post(self, request):
        """
        Allocate order to employee.
        
        Body:
            order_id: Order UUID (required)
            employee_id: Employee UUID or user_employee_id (required)
            notes: Allocation notes (optional)
        """
        company = request.company
        data = request.data
        
        # Validate required fields
        if not all(key in data for key in ['order_id', 'employee_id']):
            return Response(
                {'error': 'order_id and employee_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get order
        try:
            order = SalesOrder.objects.get(
                id=data['order_id'],
                company=company
            )
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify order can be allocated
        if order.status in ['cancelled', 'closed']:
            return Response(
                {'error': f'Cannot allocate {order.status} order'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get employee
        employee_id = data['employee_id']
        employee_name = None
        
        # Check if it's user_employee (users.Employee)
        if isinstance(employee_id, str) and employee_id.startswith('user_'):
            try:
                emp_id = int(employee_id.replace('user_', ''))
                user_emp = UserEmployee.objects.get(
                    employee_id=emp_id,
                    company=company,
                    is_active=True
                )
                employee_name = user_emp.user.get_full_name() if user_emp.user else f"Employee {emp_id}"
            except (ValueError, UserEmployee.DoesNotExist):
                return Response(
                    {'error': 'Employee not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Check hr.Employee
            try:
                hr_emp = Employee.objects.get(
                    id=employee_id,
                    company=company,
                    is_active=True
                )
                employee_name = hr_emp.name
            except Employee.DoesNotExist:
                return Response(
                    {'error': 'Employee not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Update order with allocation info
        # Note: SalesOrder model doesn't have allocated_to field currently
        # Storing in notes field as a workaround
        allocation_note = f"Allocated to: {employee_name}"
        if data.get('notes'):
            allocation_note += f" | Notes: {data['notes']}"
        
        # Append to existing notes or create new
        if order.notes:
            order.notes = f"{order.notes}\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {allocation_note}"
        else:
            order.notes = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {allocation_note}"
        
        order.save(update_fields=['notes', 'updated_at'])
        
        return Response({
            'success': True,
            'message': f'Order {order.order_number} allocated to {employee_name}',
            'order_id': str(order.id),
            'order_number': order.order_number,
            'employee_name': employee_name,
            'allocated_at': timezone.now().isoformat()
        })
