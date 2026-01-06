from django.contrib import admin
from .models import (
    Currency, Company, Address, CompanyFeature, 
    CompanyUser, FinancialYear, Sequence
)

admin.site.register(Currency)
admin.site.register(Company)
admin.site.register(Address)
admin.site.register(CompanyFeature)
admin.site.register(CompanyUser)
admin.site.register(FinancialYear)
admin.site.register(Sequence)
