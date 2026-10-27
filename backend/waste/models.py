from django.db import models

from accounts.models import Farmer, Ward
from pests.models import SprayLog


class WasteLog(models.Model):
    class WasteType(models.TextChoices):
        CROP_RESIDUE = "CROP_RESIDUE", "Crop residue"
        CHEMICAL_CONTAINER = "CHEMICAL_CONTAINER", "Chemical container"
        PACKAGING = "PACKAGING", "Packaging"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="waste_logs")
    spray_log = models.ForeignKey(
        SprayLog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="waste_logs",
    )
    waste_type = models.CharField(max_length=24, choices=WasteType.choices)
    action = models.CharField(max_length=160)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]


class DisposalPoint(models.Model):
    name = models.CharField(max_length=160)
    type = models.CharField(max_length=80)
    lat = models.FloatField()
    lng = models.FloatField()
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="disposal_points")
    hours = models.CharField(max_length=120, blank=True)
    contact = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.name
