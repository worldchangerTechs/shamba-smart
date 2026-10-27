from collections import defaultdict
from datetime import date

import requests
from django.conf import settings
from django.utils import timezone

from weather.models import WeatherSnapshot

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = "precipitation_sum,temperature_2m_min,temperature_2m_max"
HOURLY_FIELDS = "precipitation,temperature_2m,relative_humidity_2m"


def _fetch(url, params):
    response = requests.get(
        url,
        params=params,
        timeout=getattr(settings, "OPEN_METEO_TIMEOUT", 20),
    )
    response.raise_for_status()
    payload = response.json()
    if "daily" not in payload or "hourly" not in payload:
        raise ValueError("Open-Meteo response did not contain daily and hourly weather data.")
    return payload


def _daily_records(payload, today):
    daily = payload["daily"]
    hourly = payload["hourly"]
    times = daily.get("time", [])
    dates = hourly.get("time", [])
    values = {
        "rain": daily.get("precipitation_sum", []),
        "temp_min": daily.get("temperature_2m_min", []),
        "temp_max": daily.get("temperature_2m_max", []),
    }
    hourly_values = {
        "rain": hourly.get("precipitation", []),
        "temperature": hourly.get("temperature_2m", []),
        "humidity": hourly.get("relative_humidity_2m", []),
    }
    if not times:
        raise ValueError("Open-Meteo response contained no daily weather records.")
    grouped_hours = defaultdict(list)
    for index, timestamp in enumerate(dates):
        day = timestamp[:10]
        hour = {
            "time": timestamp,
            "precipitation": _number_at(hourly_values["rain"], index),
            "temperature_2m": _number_at(hourly_values["temperature"], index),
            "relative_humidity_2m": _number_at(hourly_values["humidity"], index),
        }
        grouped_hours[day].append(hour)

    records = []
    for index, day in enumerate(times):
        hours = grouped_hours[day]
        humidity_values = [
            hour["relative_humidity_2m"]
            for hour in hours
            if hour["relative_humidity_2m"] is not None
        ]
        if not hours:
            raise ValueError(f"Open-Meteo response has no hourly observations for {day}.")
        if not humidity_values:
            raise ValueError(f"Open-Meteo response has no humidity observations for {day}.")
        records.append(
            {
                "date": date.fromisoformat(day),
                "rain_mm": _required_number(values["rain"], index, "precipitation_sum"),
                "temp_min": _required_number(values["temp_min"], index, "temperature_2m_min"),
                "temp_max": _required_number(values["temp_max"], index, "temperature_2m_max"),
                "humidity": sum(humidity_values) / len(humidity_values),
                "forecast_json": {
                    "source": "open-meteo",
                    "is_forecast": date.fromisoformat(day) >= today,
                    "hourly": hours,
                },
            }
        )
    return records


def _number_at(values, index):
    if index >= len(values) or values[index] is None:
        return None
    return float(values[index])


def _required_number(values, index, name):
    value = _number_at(values, index)
    if value is None:
        raise ValueError(f"Open-Meteo response is missing {name} at index {index}.")
    return value


def fetch_ward_weather(ward, today=None):
    today = today or timezone.localdate()
    payload = _fetch(
        FORECAST_URL,
        {
            "latitude": ward.lat,
            "longitude": ward.lng,
            "daily": DAILY_FIELDS,
            "hourly": HOURLY_FIELDS,
            "timezone": "auto",
            "past_days": 30,
            "forecast_days": 14,
        },
    )
    return _daily_records(payload, today=today)


def store_ward_weather(ward, today=None):
    records = fetch_ward_weather(ward, today=today)
    snapshots = []
    for record in records:
        snapshot, _ = WeatherSnapshot.objects.update_or_create(
            ward=ward,
            date=record["date"],
            defaults={
                "rain_mm": record["rain_mm"],
                "temp_min": record["temp_min"],
                "temp_max": record["temp_max"],
                "humidity": record["humidity"],
                "forecast_json": record["forecast_json"],
            },
        )
        snapshots.append(snapshot)
    return snapshots
