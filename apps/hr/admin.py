from django.contrib import admin
from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'is_active', 'created_at')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'code')
    ordering = ('company', 'name')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'first_name', 'last_name', 'email', 'department', 'designation', 'is_active', 'company')
    list_filter = ('is_active', 'department', 'company')
    search_fields = ('employee_code', 'first_name', 'last_name', 'email')
    ordering = ('company', 'employee_code')
    date_hierarchy = 'date_of_joining'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('employee_code', 'user', 'company')
        }),
        ('Personal Details', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Employment Details', {
            'fields': ('department', 'designation', 'date_of_joining', 'date_of_exit', 'is_active')
        }),
    )

