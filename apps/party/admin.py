from django.contrib import admin
from .models import Party, PartyAddress, PartyBankAccount

admin.site.register(Party)
admin.site.register(PartyAddress)
admin.site.register(PartyBankAccount)
