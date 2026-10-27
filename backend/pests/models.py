from django.conf import settings
from django.db import models

from accounts.models import Farmer, Ward
from farms.models import Crop, Farm


class PestReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        NEEDS_INFO = "NEEDS_INFO", "More information requested"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"

    class PestName(models.TextChoices):
        FALL_ARMYWORM = "fall_armyworm", "Fall armyworm"
        APHIDS = "aphids", "Aphids"
        WHITEFLY = "whitefly", "Whitefly"
        TOMATO_LEAFMINER = "tomato_leafminer", "Tomato leafminer (Tuta absoluta)"
        LATE_BLIGHT = "late_blight", "Late blight"
        COFFEE_BERRY_DISEASE = "coffee_berry_disease", "Coffee berry disease"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="pest_reports")
    farm = models.ForeignKey(Farm, null=True, blank=True, on_delete=models.SET_NULL, related_name="pest_reports")
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL, related_name="pest_reports")
    photo = models.ImageField(upload_to="pest-reports/%Y/%m/", null=True, blank=True)
    description = models.TextField(blank=True)
    symptoms = models.TextField(blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="pest_reports")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    verification_note = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_pest_reports",
        limit_choices_to={"role": "OFFICER"},
    )
    pest_name = models.CharField(max_length=32, choices=PestName.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Outbreak(models.Model):
    class Level(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="outbreaks")
    pest_name = models.CharField(max_length=120)
    crop = models.ForeignKey(Crop, null=True, blank=True, on_delete=models.SET_NULL, related_name="outbreaks")
    started_at = models.DateTimeField()
    confirmed_count = models.PositiveIntegerField(default=0)
    level = models.CharField(max_length=10, choices=Level.choices)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ward", "pest_name"],
                name="unique_outbreak_ward_pest",
            )
        ]


class PestKnowledge(models.Model):
    pest_name = models.CharField(max_length=32, choices=PestReport.PestName.choices, unique=True)
    symptom_icons = models.JSONField(default=list)
    symptoms_by_language = models.JSONField(default=dict)
    safe_actions_by_language = models.JSONField(default=dict)
    ipm_by_language = models.JSONField(default=dict)
    call_officer_by_language = models.JSONField(default=dict)
    photo = models.ImageField(upload_to="pest-knowledge/", null=True, blank=True)

    class Meta:
        ordering = ["pest_name"]

    def __str__(self):
        return self.get_pest_name_display()


class SprayLog(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="spray_logs")
    product_name = models.CharField(max_length=160)
    active_ingredient = models.CharField(max_length=160)
    sprayed_at = models.DateTimeField()
    ppe_checked = models.BooleanField(default=False)
    reentry_hours = models.PositiveIntegerField()
    pre_harvest_days = models.PositiveIntegerField()

    class Meta:
        ordering = ["-sprayed_at"]
