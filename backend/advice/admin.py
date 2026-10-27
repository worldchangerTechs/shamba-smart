from django.contrib import admin

from .models import AdviceContent, AdviceRecommendation, PpeSupplier

admin.site.register((AdviceRecommendation, AdviceContent, PpeSupplier))
