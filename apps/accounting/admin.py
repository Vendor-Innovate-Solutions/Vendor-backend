from django.contrib import admin
from .models import AccountGroup, Ledger, TaxLedger, CostCenter, LedgerBalance

admin.site.register(AccountGroup)
admin.site.register(Ledger)
admin.site.register(TaxLedger)
admin.site.register(CostCenter)
admin.site.register(LedgerBalance)
