from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Ward
from weather.models import WeatherSnapshot


def _sample_record(day, index, forecast):
    rain_mm = 36.0 if forecast and index == 2 else (
        3.0 if (index + (0 if forecast else 1)) % 5 == 0 else 0.0
    )
    hourly = []
    if forecast:
        rain_hours = 8 if index == 2 else (3 if rain_mm else 0)
        hourly = [
            {
                "time": datetime.combine(day, time(hour=hour)).isoformat(),
                "precipitation": round(rain_mm / rain_hours, 2)
                if hour < rain_hours
                else 0.0,
                "temperature_2m": round(17 + 5 * (hour / 23), 1),
                "relative_humidity_2m": 78 if rain_mm else 66,
            }
            for hour in range(24)
        ]
    return {
        "rain_mm": rain_mm,
        "temp_min": 14.0 + index % 3,
        "temp_max": 24.0 + index % 4,
        "humidity": 78.0 if rain_mm else 66.0,
        "forecast_json": {
            "source": "demo",
            "is_forecast": forecast,
            "hourly": hourly,
        },
    }


class Command(BaseCommand):
    help = "Seed clearly labelled sample weather history and forecasts for configured wards."

    @transaction.atomic
    def handle(self, *args, **options):
        wards = list(Ward.objects.order_by("pk"))
        if not wards:
            raise CommandError("Create demo wards first with seed_demo.")

        today = timezone.localdate()
        created = updated = skipped = 0
        for ward_index, ward in enumerate(wards):
            records = [
                (today - timedelta(days=offset), 30 - offset, False)
                for offset in range(30, 0, -1)
            ]
            records.extend(
                (today + timedelta(days=offset), offset, True)
                for offset in range(14)
            )
            for day, index, forecast in records:
                values = _sample_record(day, index + ward_index, forecast)
                snapshot, was_created = WeatherSnapshot.objects.get_or_create(
                    ward=ward,
                    date=day,
                    defaults=values,
                )
                if was_created:
                    created += 1
                elif snapshot.forecast_json.get("source") == "demo":
                    for field, value in values.items():
                        setattr(snapshot, field, value)
                    snapshot.save(update_fields=tuple(values))
                    updated += 1
                else:
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo weather ready: {created} created, {updated} refreshed, "
                f"{skipped} existing live snapshots preserved across {len(wards)} wards."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "These are synthetic sample weather records, not an actual forecast."
            )
        )
