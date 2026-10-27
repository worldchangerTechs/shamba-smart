from django.conf import settings
from django.db import models


class SmsBatch(models.Model):
    class Provider(models.TextChoices):
        VENDEL = "vendel", "Vendel"
        SIMULATOR = "simulator", "Simulator"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sms_batches",
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    provider_batch_id = models.CharField(max_length=255, blank=True)
    template_code = models.CharField(max_length=80)
    target_description = models.CharField(max_length=255)
    severity = models.CharField(max_length=10)
    total = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SmsMessage(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        SENT = "SENT", "Sent"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"

    batch = models.ForeignKey(
        SmsBatch, on_delete=models.CASCADE, related_name="messages"
    )
    farmer = models.ForeignKey(
        "accounts.Farmer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_messages",
    )
    alert = models.ForeignKey(
        "alerts.Alert",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_messages",
    )
    phone = models.CharField(max_length=16)
    body = models.CharField(max_length=160)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["batch", "status"])]


class SmsSkippedRecipient(models.Model):
    batch = models.ForeignKey(
        SmsBatch, on_delete=models.CASCADE, related_name="skipped_recipients"
    )
    farmer = models.ForeignKey(
        "accounts.Farmer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="skipped_sms_messages",
    )
    phone = models.CharField(max_length=16, blank=True)
    reason = models.CharField(max_length=80)

    class Meta:
        ordering = ["pk"]


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sms_audit_events",
    )
    batch = models.OneToOneField(
        SmsBatch, on_delete=models.CASCADE, related_name="audit_log"
    )
    template_code = models.CharField(max_length=80)
    target_description = models.CharField(max_length=255)
    count = models.PositiveIntegerField()
    provider = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
