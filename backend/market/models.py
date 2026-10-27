from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

from accounts.models import Farmer, Ward
from farms.models import Crop


class MarketPrice(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="market_prices")
    market_name = models.CharField(max_length=160)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="market_prices")
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    date = models.DateField()
    is_sample_data = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["crop", "market_name", "ward", "date"],
                name="unique_market_crop_ward_date",
            )
        ]

    def __str__(self):
        marker = " (sample)" if self.is_sample_data else ""
        return f"{self.crop} at {self.market_name}: KES {self.price_per_kg}/kg{marker}"


class Buyer(models.Model):
    class BuyerType(models.TextChoices):
        SUPERMARKET = "SUPERMARKET", "Supermarket"
        EXPORTER = "EXPORTER", "Exporter"
        HOTEL = "HOTEL", "Hotel"
        COOPERATIVE = "COOPERATIVE", "Cooperative"
        AGGREGATOR = "AGGREGATOR", "Aggregator"

    name = models.CharField(max_length=160)
    type = models.CharField(max_length=20, choices=BuyerType.choices)
    crops = models.ManyToManyField(Crop, related_name="buyers", blank=True)
    contact = models.CharField(max_length=120)
    verified = models.BooleanField(default=False)
    ward = models.ForeignKey(
        Ward, null=True, blank=True, on_delete=models.SET_NULL, related_name="buyers"
    )
    is_sample_data = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class TrainingEvent(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateTimeField()
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="training_events")
    host = models.CharField(max_length=160)
    link = models.URLField(blank=True)
    event_type = models.CharField(max_length=40, default="TRAINING")
    is_sample_data = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]


class SellListing(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        SOLD = "SOLD", "Sold"
        CLOSED = "CLOSED", "Closed"

    farmer = models.ForeignKey(
        Farmer, on_delete=models.CASCADE, related_name="sell_listings"
    )
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="sell_listings")
    quantity_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    harvest_date = models.DateField()
    asking_price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    is_sample_data = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["harvest_date", "-created_at"]

    def __str__(self):
        return f"{self.crop}: {self.quantity_kg} kg ({self.status})"
