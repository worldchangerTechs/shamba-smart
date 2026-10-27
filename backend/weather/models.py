from django.db import models

from accounts.models import Ward


class WeatherSnapshot(models.Model):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="weather_snapshots")
    date = models.DateField()
    rain_mm = models.FloatField()
    temp_min = models.FloatField()
    temp_max = models.FloatField()
    humidity = models.FloatField()
    forecast_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["ward", "date"], name="unique_weather_per_ward_date")
        ]

    def __str__(self):
        return f"{self.ward} weather on {self.date}"
