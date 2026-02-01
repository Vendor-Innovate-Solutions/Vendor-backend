"""
HR and Payroll models for ERP system.
Models: Department, Employee, EmployeeLedger, PayHead, EmployeePayStructure, PayrollRun
"""
from django.db import models
from django.conf import settings
from core.models import CompanyScopedModel, BaseModel


class Department(CompanyScopedModel):
    """
    Department/team organization.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    
    manager = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_departments'
    )
    
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='sub_departments'
    )
    
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Employee(CompanyScopedModel):
    """
    Employee master.
    Note: Employee is separate from Party for HR-specific tracking.
    """
    employee_code = models.CharField(max_length=50, db_index=True)
    
    # Optional link to user account
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profiles'
    )
    
    # Personal details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    
    # Employment details
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name='employees'
    )
    
    designation = models.CharField(max_length=100)
    
    date_of_joining = models.DateField()
    date_of_exit = models.DateField(
        null=True,
        blank=True,
        help_text="Date when employee left"
    )
    
    # Status
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "employee_code")
        verbose_name_plural = "Employees"
        indexes = [
            models.Index(fields=['company', 'employee_code']),
            models.Index(fields=['company', 'department', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.employee_code} - {self.first_name} {self.last_name}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


class EmployeeLedger(BaseModel):
    """
    Links employee to accounting ledger.
    Every employee has an associated expense/payable ledger.
    """
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='ledger_link'
    )
    
    ledger = models.ForeignKey(
        "accounting.Ledger",
        on_delete=models.PROTECT,
        related_name='employee_ledgers'
    )

    class Meta:
        verbose_name_plural = "Employee Ledgers"

    def __str__(self):
        return f"{self.employee.name} → {self.ledger.name}"


class PayType(models.TextChoices):
    """Enum for pay head types"""
    EARNING = 'EARNING', 'Earning'
    DEDUCTION = 'DEDUCTION', 'Deduction'
    REIMBURSEMENT = 'REIMBURSEMENT', 'Reimbursement'


class PayHead(CompanyScopedModel):
    """
    Salary components (earning/deduction heads).
    Examples: Basic Salary, HRA, PF, Professional Tax, etc.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    
    pay_type = models.CharField(
        max_length=20,
        choices=PayType.choices
    )
    
    is_taxable = models.BooleanField(
        default=True,
        help_text="Whether this component is taxable"
    )
    
    is_fixed = models.BooleanField(
        default=True,
        help_text="Fixed amount vs percentage-based"
    )
    
    calculation_formula = models.TextField(
        blank=True,
        help_text="Formula for computation (if percentage-based)"
    )
    
    ledger = models.ForeignKey(
        "accounting.Ledger",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='pay_heads',
        help_text="Accounting ledger for this pay component"
    )
    
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Pay Heads"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'pay_type']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.pay_type})"


class EmployeePayStructure(BaseModel):
    """
    Pay structure for individual employees.
    Time-bounded to handle salary revisions.
    """
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='pay_structure'
    )
    
    pay_head = models.ForeignKey(
        PayHead,
        on_delete=models.CASCADE,
        related_name='employee_assignments'
    )
    
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Fixed amount or percentage value"
    )
    
    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text="End date for this structure (null = current)"
    )

    class Meta:
        verbose_name_plural = "Employee Pay Structures"
        indexes = [
            models.Index(fields=['employee', 'effective_from']),
            models.Index(fields=['pay_head', 'effective_from']),
        ]

    def __str__(self):
        return f"{self.employee.name} - {self.pay_head.name}: {self.amount}"


class PayrollStatus(models.TextChoices):
    """Enum for payroll run status"""
    DRAFT = 'DRAFT', 'Draft'
    PROCESSED = 'PROCESSED', 'Processed'
    POSTED = 'POSTED', 'Posted to Accounts'
    PAID = 'PAID', 'Paid'
    CANCELLED = 'CANCELLED', 'Cancelled'


class PayrollRun(CompanyScopedModel):
    """
    Monthly payroll processing run.
    Groups all employee payslips for a period.
    Creates a single accounting voucher for the entire payroll.
    """
    name = models.CharField(
        max_length=100,
        help_text="E.g., 'January 2024 Payroll'"
    )
    
    pay_period_start = models.DateField()
    pay_period_end = models.DateField()
    
    payment_date = models.DateField(
        help_text="Date when salaries will be paid"
    )
    
    status = models.CharField(
        max_length=20,
        choices=PayrollStatus.choices,
        default=PayrollStatus.DRAFT
    )
    
    # Link to accounting voucher
    voucher = models.OneToOneField(
        "voucher.Voucher",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='payroll_run',
        help_text="Accounting voucher for this payroll"
    )
    
    # Summary amounts
    total_earnings = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    total_deductions = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    net_pay = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Payroll Runs"
        indexes = [
            models.Index(fields=['company', 'pay_period_start', 'pay_period_end']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pay_period_start__lt=models.F('pay_period_end')),
                name="payroll_period_start_before_end",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.pay_period_start} to {self.pay_period_end})"
