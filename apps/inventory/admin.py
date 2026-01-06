from django.contrib import admin
from .models import (
    UnitOfMeasure, StockItem, PriceList, ItemPrice,
    StockBatch, Godown, StockMovement, StockBalance
)

admin.site.register(UnitOfMeasure)
admin.site.register(StockItem)
admin.site.register(PriceList)
admin.site.register(ItemPrice)
admin.site.register(StockBatch)
admin.site.register(Godown)
admin.site.register(StockMovement)
admin.site.register(StockBalance)
