from django.contrib import admin
from .models import RetailerUser, RetailerCompanyAccess


@admin.register(RetailerUser)
class RetailerUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'party', 'is_primary_contact', 'can_place_orders')
    list_filter = ('is_primary_contact', 'can_place_orders', 'can_view_balance')
    search_fields = ('user__username', 'user__email', 'party__name')
    raw_id_fields = ('user', 'party')


@admin.register(RetailerCompanyAccess)
class RetailerCompanyAccessAdmin(admin.ModelAdmin):
    list_display = ('retailer', 'company', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('retailer__user__username', 'company__name')
    raw_id_fields = ('retailer', 'company')
    date_hierarchy = 'created_at'
