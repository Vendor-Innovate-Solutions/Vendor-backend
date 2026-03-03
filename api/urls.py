"""
API URL configuration - Central routing for all API endpoints.
"""
from django.urls import path, include

urlpatterns = [
    # User APIs (Registration, OTP)
    path('users/', include('apps.users.urls')),
    
    # Company APIs (Financial Year, etc.)
    path('company/', include('apps.company.api.urls')),
    
    # Accounting APIs
    path('accounting/', include('apps.accounting.api.urls')),
    
    # Products APIs (Catalog Management)
    path('catalog/', include('apps.products.api.urls')),
    
    # Inventory APIs
    path('inventory/', include('apps.inventory.api.urls')),    
    
    # Order APIs
    path('orders/', include('apps.orders.api.urls')),
    
    # Invoice APIs
    path('invoices/', include('apps.invoice.api.urls')),
    
    # Payment APIs
    path('payments/', include('apps.voucher.api.urls')),
    
    # Party APIs (Credit Control)
    path('party/', include('apps.party.api.urls')),
    
    # Portal APIs (Retailer features)
    path('portal/', include('apps.portal.api.urls')),
    
    # Pricing APIs
    path('pricing/', include('apps.pricing.api.urls')),
    
    # GST APIs (Compliance)
    path('gst/', include('integrations.gst.api.urls')),
    
    # Workflow APIs (Approval Management)
    path('workflow/', include('apps.workflow.api.urls')),
    
    # Reporting APIs (Aging Reports)
    path('reports/', include('apps.reporting.api.urls')),
    
    # System APIs (Tally Import, etc.)
    path('system/', include('apps.system.tally_import.urls')),

    # Razorpay Payment Integration
    path('payments/', include('integrations.payments.urls')),
]
