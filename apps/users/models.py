"""
User and authentication related models.
Models: Employee, PasswordResetOTP
Note: Retailer models moved to apps.portal
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string


class Employee(models.Model):
    """
    Internal company employee.
    Links User to Company for HR and operational purposes.
    """
    employee_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name="employees"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        null=True,
        blank=True
    )
    
    # Employee details
    contact = models.CharField(max_length=20, default="Not Provided")
    designation = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.company.name}"
        return f"Employee {self.employee_id} - {self.company.name}"


class PasswordResetOTP(models.Model):
    """
    OTP-based password reset mechanism.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_otps"
    )
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.otp:
            self.otp = self.generate_otp()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)  # OTP expires in 10 minutes
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"OTP for {self.user.username} - {self.otp}"
    
    class Meta:
        ordering = ['-created_at']
