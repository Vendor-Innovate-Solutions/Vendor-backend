from django.contrib import admin
from .models import Carrier, Shipment, ShipmentItem

admin.site.register(Carrier)
admin.site.register(Shipment)
admin.site.register(ShipmentItem)
