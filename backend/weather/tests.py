import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from accounts.models import Farmer, User, Ward
from farms.models import Crop, Farm
from weather.models import WeatherSnapshot
from weather.services.mvua_planner import (
    planting_window,
    rain_alerts,
    sms_versions,
)


FORECAST_FIXTURE = (
    Path(__file__).parent / "fixtures" / "mvua_forecast.json"
)
class MvuaPlannerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=-0.6773, lng=34.7792
        )
        cls.crop = Crop.objects.create(
            name="Potato",
            water_needs="Moderate",
            ideal_ph_min=5.0,
            ideal_ph_max=6.5,
        )
        cls.user = User.objects.create_user(phone="+254720000001", role=User.Role.FARMER)
        cls.farmer = Farmer.objects.create(
            user=cls.user,
            ward=cls.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
            has_smartphone=True,
        )
        cls.farm = Farm.objects.create(
            farmer=cls.farmer,
            name="Test farm",
            lat=-0.6773,
            lng=34.7792,
            size_acres=1,
            slope_class=Farm.SlopeClass.GENTLE,
            soil_type="loam",
        )

    def setUp(self):
        fixture = json.loads(FORECAST_FIXTURE.read_text(encoding="utf-8"))
        self.today = timezone.localdate()
        self.daily = fixture["daily"]
        hourly_rain_by_day = fixture["hourly_rain_by_day"]

        for index in range(30):
            day = self.today - timedelta(days=30 - index)
            WeatherSnapshot.objects.create(
                ward=self.ward,
                date=day,
                rain_mm=0,
                temp_min=14,
                temp_max=24,
                humidity=75,
                forecast_json={"source": "open-meteo", "is_forecast": False, "hourly": []},
            )

        for index in range(14):
            day = self.today + timedelta(days=index)
            values = hourly_rain_by_day.get(str(index), [])
            hourly = []
            for hour in range(24):
                rainfall = values[hour] if hour < len(values) else 0
                timestamp = datetime.combine(day, time(hour=hour)).isoformat()
                hourly.append(
                    {
                        "time": timestamp,
                        "precipitation": rainfall,
                        "temperature_2m": 20,
                        "relative_humidity_2m": self.daily[index]["humidity"],
                    }
                )
            WeatherSnapshot.objects.create(
                ward=self.ward,
                date=day,
                rain_mm=self.daily[index]["rain_mm"],
                temp_min=self.daily[index]["temp_min"],
                temp_max=self.daily[index]["temp_max"],
                humidity=self.daily[index]["humidity"],
                forecast_json={
                    "source": "open-meteo",
                    "is_forecast": True,
                    "hourly": hourly,
                },
            )

    def test_open_meteo_forecast_fetch_requests_30_past_and_14_forecast_days(self):
        from weather.services.open_meteo import fetch_ward_weather

        payload = {
            "daily": {
                "time": [self.today.isoformat()],
                "precipitation_sum": [4],
                "temperature_2m_min": [12],
                "temperature_2m_max": [24],
            },
            "hourly": {
                "time": [f"{self.today.isoformat()}T{hour:02}:00" for hour in range(24)],
                "precipitation": [1] * 24,
                "temperature_2m": [18] * 24,
                "relative_humidity_2m": [70] * 24,
            },
        }
        with patch("weather.services.open_meteo._fetch", return_value=payload) as fetch:
            records = fetch_ward_weather(self.ward, today=self.today)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rain_mm"], 4)
        self.assertEqual(records[0]["humidity"], 70)
        self.assertTrue(records[0]["forecast_json"]["is_forecast"])
        params = fetch.call_args.args[1]
        self.assertEqual(params["past_days"], 30)
        self.assertEqual(params["forecast_days"], 14)

    def test_snapshot_storage_updates_existing_ward_date(self):
        from weather.services.open_meteo import store_ward_weather

        record = {
            "date": self.today,
            "rain_mm": 8,
            "temp_min": 12,
            "temp_max": 23,
            "humidity": 72,
            "forecast_json": {"source": "open-meteo", "is_forecast": True, "hourly": []},
        }
        with patch("weather.services.open_meteo.fetch_ward_weather", return_value=[record]):
            store_ward_weather(self.ward, today=self.today)
            record["rain_mm"] = 12
            store_ward_weather(self.ward, today=self.today)
        self.assertEqual(
            WeatherSnapshot.objects.filter(ward=self.ward, date=self.today).count(),
            1,
        )
        self.assertEqual(
            WeatherSnapshot.objects.get(ward=self.ward, date=self.today).rain_mm,
            12,
        )

    def test_planting_window_recommends_when_rain_is_imminent(self):
        result = planting_window(self.crop, self.ward, today=self.today)
        self.assertEqual(result["status"], "RECOMMENDED_NOW")
        self.assertIn("suitable", result["reason"])

    def test_planting_window_waits_for_later_forecast_rain(self):
        for snapshot in WeatherSnapshot.objects.filter(
            ward=self.ward,
            date__gte=self.today,
            forecast_json__is_forecast=True,
        ):
            rain = 11 if snapshot.date in (self.today + timedelta(days=7), self.today + timedelta(days=8)) else 0
            snapshot.rain_mm = rain
            snapshot.save(update_fields=["rain_mm"])
        result = planting_window(self.crop, self.ward, today=self.today)
        self.assertEqual(result["status"], "WAIT_7_DAYS")
        self.assertEqual(result["wait_days"], 7)

    def test_planting_window_marks_persistently_dry_conditions(self):
        WeatherSnapshot.objects.filter(
            ward=self.ward,
            date__gte=self.today - timedelta(days=30),
            date__lte=self.today + timedelta(days=13),
        ).update(rain_mm=0)
        result = planting_window(self.crop, self.ward, today=self.today)
        self.assertEqual(result["status"], "TOO_DRY")
        self.assertIsNone(result["wait_days"])

    def test_rain_alerts_cover_heavy_rain_dry_spell_blight_and_cold_nights(self):
        alerts = rain_alerts(self.ward, crop=self.crop, today=self.today)
        codes = {alert["code"] for alert in alerts}
        self.assertTrue(
            {"HEAVY_RAIN", "DRY_SPELL", "BLIGHT_CONDITIONS", "COLD_NIGHT"} <= codes,
            codes,
        )
        heavy_rain = next(alert for alert in alerts if alert["code"] == "HEAVY_RAIN")
        self.assertGreater(heavy_rain["rain_mm"], 25)

    def test_sms_versions_are_short_and_include_all_languages(self):
        sms = sms_versions("WAIT_3_DAYS", wait_days=3)
        self.assertEqual(set(sms), {"en", "sw", "guz"})
        self.assertTrue(all(len(message) < 160 for message in sms.values()))

    def test_planner_and_weather_endpoints_are_farm_scoped(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get(f"/api/farms/{self.farm.pk}/planner/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("calendar", response.data)
        self.assertTrue(
            all(
                {"plant", "weed", "top_dress", "spray_window", "harvest"} <= set(week)
                for week in response.data["calendar"]["weeks"]
            )
        )
        self.assertEqual(set(response.data["sms"]), {"en", "sw", "guz"})
        self.assertTrue(
            all(len(message) < 160 for message in response.data["sms"].values())
        )

        response = client.get(f"/api/farms/{self.farm.pk}/weather/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 44)

        other_user = User.objects.create_user(phone="+254720000002", role=User.Role.FARMER)
        Farmer.objects.create(
            user=other_user,
            ward=self.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        client.force_authenticate(user=other_user)
        response = client.get(f"/api/farms/{self.farm.pk}/planner/")
        self.assertEqual(response.status_code, 404)


class WeatherRefreshTaskTests(TestCase):
    def test_refresh_schedule_runs_every_six_hours(self):
        schedule = settings.CELERY_BEAT_SCHEDULE[
            "refresh-ward-weather-every-six-hours"
        ]["schedule"]
        self.assertEqual(schedule.run_every, timedelta(hours=6))

    def test_refresh_task_updates_each_ward(self):
        ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=-0.79, lng=34.72
        )
        with patch("weather.tasks.store_ward_weather", return_value=[object()] * 44) as store:
            from weather.tasks import refresh_weather_snapshots

            result = refresh_weather_snapshots.run()
        self.assertEqual(result, {"wards": 1, "snapshots": 44})
        store.assert_called_once()
        self.assertEqual(store.call_args.args[0], ward)


class WeatherDemoSeedTests(TestCase):
    def setUp(self):
        self.ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=-0.79, lng=34.72
        )

    def test_seed_weather_demo_creates_idempotent_sample_history_and_forecast(self):
        from django.core.management import call_command

        call_command("seed_weather_demo", verbosity=0)
        call_command("seed_weather_demo", verbosity=0)

        snapshots = WeatherSnapshot.objects.filter(ward=self.ward)
        self.assertEqual(snapshots.count(), 44)
        self.assertEqual(
            snapshots.filter(forecast_json__source="demo").count(),
            44,
        )
        forecast = snapshots.get(date=timezone.localdate() + timedelta(days=2))
        self.assertTrue(forecast.forecast_json["is_forecast"])
        self.assertEqual(len(forecast.forecast_json["hourly"]), 24)
        self.assertAlmostEqual(
            sum(
                hour["precipitation"]
                for hour in forecast.forecast_json["hourly"]
            ),
            forecast.rain_mm,
            places=1,
        )

    def test_seed_weather_demo_preserves_live_snapshots(self):
        from django.core.management import call_command

        snapshot = WeatherSnapshot.objects.create(
            ward=self.ward,
            date=timezone.localdate(),
            rain_mm=8,
            temp_min=12,
            temp_max=23,
            humidity=72,
            forecast_json={"source": "open-meteo", "is_forecast": True, "hourly": []},
        )
        call_command("seed_weather_demo", verbosity=0)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.rain_mm, 8)
        self.assertEqual(snapshot.forecast_json["source"], "open-meteo")
