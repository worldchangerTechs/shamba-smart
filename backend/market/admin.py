from django.contrib import admin

from .models import Buyer, MarketPrice, SellListing, TrainingEvent

admin.site.register((MarketPrice, Buyer, TrainingEvent, SellListing))
