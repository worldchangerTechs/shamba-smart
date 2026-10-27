from django.conf import settings
from django.db import models

from accounts.models import Farmer


class Crop(models.Model):
    name = models.CharField(max_length=120, unique=True)
    local_name_sw = models.CharField(max_length=120, blank=True)
    local_name_guz = models.CharField(max_length=120, blank=True)
    water_needs = models.CharField(max_length=120)
    ideal_ph_min = models.FloatField()
    ideal_ph_max = models.FloatField()
    common_pests = models.JSONField(default=list, blank=True)
    common_diseases = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Farm(models.Model):
    class SlopeClass(models.TextChoices):
        FLAT = "FLAT", "Flat"
        GENTLE = "GENTLE", "Gentle"
        STEEP = "STEEP", "Steep"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="farms")
    name = models.CharField(max_length=120)
    lat = models.FloatField()
    lng = models.FloatField()
    size_acres = models.DecimalField(max_digits=8, decimal_places=2)
    slope_class = models.CharField(max_length=8, choices=SlopeClass.choices)
    soil_type = models.CharField(max_length=120)
    soil_ph = models.FloatField(null=True, blank=True)
    last_lime_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.farmer.user.phone})"


class Planting(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="plantings")
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="plantings")
    variety = models.CharField(max_length=120)
    planted_on = models.DateField()
    expected_harvest = models.DateField()

    class Meta:
        ordering = ["-planted_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["farm", "crop", "planted_on"], name="unique_farm_crop_planting_date"
            )
        ]

    def __str__(self):
        return f"{self.crop} at {self.farm}"
