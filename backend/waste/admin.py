from django.contrib import admin

from .models import DisposalPoint, WasteLog

admin.site.register((WasteLog, DisposalPoint))
