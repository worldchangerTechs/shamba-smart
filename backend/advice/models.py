from django.db import models

from accounts.models import Farmer
from farms.models import Farm


class AdviceRecommendation(models.Model):
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="advice")
    farm = models.ForeignKey(Farm, null=True, blank=True, on_delete=models.SET_NULL, related_name="advice")
    problem_tag = models.CharField(max_length=80, db_index=True)
    body_by_language = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]


class AdviceContent(models.Model):
    class Service(models.TextChoices):
        UDONGO = "UDONGO", "Udongo Doctor"
        SPRAY = "SPRAY", "Spray Safe"
        MTEREMKO = "MTEREMKO", "Mteremko Guard"
        TAKA = "TAKA", "Taka Loop"

    class Effort(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    code = models.SlugField(max_length=80, unique=True)
    service = models.CharField(max_length=12, choices=Service.choices, db_index=True)
    title_en = models.CharField(max_length=180)
    title_sw = models.CharField(max_length=180, blank=True)
    title_guz = models.CharField(max_length=180, blank=True)
    body_en = models.TextField()
    body_sw = models.TextField(blank=True)
    body_guz = models.TextField(blank=True)
    cost_min_kes_per_acre = models.PositiveIntegerField(null=True, blank=True)
    cost_max_kes_per_acre = models.PositiveIntegerField(null=True, blank=True)
    effort = models.CharField(
        max_length=8, choices=Effort.choices, default=Effort.LOW, blank=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["service", "code"]

    def __str__(self):
        return self.code


class PpeSupplier(models.Model):
    class SupplierType(models.TextChoices):
        AGRO_DEALER = "AGRO_DEALER", "Agro-dealer"
        COOPERATIVE = "COOPERATIVE", "Cooperative"

    name = models.CharField(max_length=160)
    supplier_type = models.CharField(max_length=16, choices=SupplierType.choices)
    ward = models.ForeignKey(
        "accounts.Ward", on_delete=models.PROTECT, related_name="ppe_suppliers"
    )
    lat = models.FloatField()
    lng = models.FloatField()
    contact = models.CharField(max_length=120, blank=True)
    item_prices_kes = models.JSONField(
        default=dict,
        help_text="Available PPE item codes mapped to their prices in KES.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
