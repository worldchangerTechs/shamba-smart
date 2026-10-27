from django.contrib import admin

from .models import Outbreak, PestKnowledge, PestReport, SprayLog

admin.site.register((PestReport, Outbreak, PestKnowledge, SprayLog))
