from django.contrib import admin

from .models import Crop, Farm, Planting

admin.site.register((Crop, Farm, Planting))
