from django.contrib import admin
from .models import Employee, PasswordResetOTP


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user', 'company', 'designation', 'is_active')
    list_filter = ('is_active', 'company')
    search_fields = ('user__username', 'user__email', 'contact', 'designation')
    raw_id_fields = ('user', 'company')


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp', 'is_verified', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'otp')
    readonly_fields = ('created_at', 'expires_at')
    date_hierarchy = 'created_at'
