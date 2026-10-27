from django.conf import settings
from django.db import models

from accounts.models import Farmer
from farms.models import Farm


class Rule(models.Model):
    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    code = models.CharField(max_length=80, unique=True)
    problem_tag = models.CharField(max_length=80, db_index=True)
    condition_json = models.JSONField(default=dict)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    message_templates = models.JSONField(default=dict)
    cooldown_hours = models.PositiveIntegerField(default=24)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Alert(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        RESOLVED = "RESOLVED", "Resolved"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="alerts")
    farm = models.ForeignKey(Farm, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    rule = models.ForeignKey(Rule, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts")
    severity = models.CharField(max_length=10, choices=Rule.Severity.choices)
    priority = models.PositiveSmallIntegerField(default=100)
    title = models.CharField(max_length=200)
    body_by_language = models.JSONField(default=dict)
    source_key = models.CharField(max_length=160, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["farmer", "rule", "source_key"],
                condition=~models.Q(source_key=""),
                name="unique_alert_source_per_farmer_rule",
            )
        ]


class RuleWardPriority(models.Model):
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="ward_priorities")
    ward = models.ForeignKey("accounts.Ward", on_delete=models.CASCADE, related_name="rule_priorities")
    priority = models.PositiveSmallIntegerField(default=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rule", "ward"], name="unique_rule_ward_priority")
        ]


class AlertDelivery(models.Model):
    class Channel(models.TextChoices):
        APP = "app", "App"
        SMS = "sms", "SMS"
        VOICE = "voice", "Voice"

    class Feedback(models.TextChoices):
        HELPFUL = "HELPFUL", "Helpful"
        NOT_RELEVANT = "NOT_RELEVANT", "Not relevant"

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=8, choices=Channel.choices)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered = models.BooleanField(default=False)
    feedback = models.CharField(max_length=16, choices=Feedback.choices, null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]
