from django.contrib import admin

from .models import AuditLog, SmsBatch, SmsMessage, SmsSkippedRecipient


@admin.register(SmsBatch)
class SmsBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "template_code",
        "target_description",
        "total",
        "created_by",
        "created_at",
    )
    list_filter = ("provider", "severity", "created_at")
    search_fields = ("template_code", "target_description", "created_by__phone")
    readonly_fields = ("created_at",)


@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "phone", "status", "created_at", "updated_at")
    list_filter = ("status", "batch__provider")
    search_fields = ("phone", "provider_message_id", "error")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SmsSkippedRecipient)
class SmsSkippedRecipientAdmin(admin.ModelAdmin):
    list_display = ("batch", "phone", "reason")
    list_filter = ("reason",)
    search_fields = ("phone",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "template_code",
        "target_description",
        "count",
        "provider",
    )
    list_filter = ("provider", "created_at")
    search_fields = ("user__phone", "template_code", "target_description")
    readonly_fields = ("created_at",)
