from django.contrib import admin
from .models import SalesOrder, PurchaseOrder, OrderItem

admin.site.register(SalesOrder)
admin.site.register(PurchaseOrder)
admin.site.register(OrderItem)
