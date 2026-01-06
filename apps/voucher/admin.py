from django.contrib import admin
from .models import VoucherType, Voucher, VoucherLine

admin.site.register(VoucherType)
admin.site.register(Voucher)
admin.site.register(VoucherLine)
