from datetime import datetime, timedelta

from django.utils import timezone

from weather.models import WeatherSnapshot

DRY_DAY_MM = 1
RECOMMENDED_HISTORY_MM = 30
RECOMMENDED_FORECAST_MM = 15
PLANTING_RAIN_MM = 10
VERY_DRY_HISTORY_MM = 15
VERY_DRY_FORECAST_MM = 20


def _forecast_rows(ward, start, end):
    return list(
        WeatherSnapshot.objects.filter(
            ward=ward,
            date__gte=start,
            date__lte=end,
            forecast_json__is_forecast=True,
        ).order_by("date")
    )


def _history_rows(ward, start, end):
    return list(
        WeatherSnapshot.objects.filter(
            ward=ward,
            date__gte=start,
            date__lte=end,
            forecast_json__is_forecast=False,
        ).order_by("date")
    )


def planting_window(crop, ward, today=None):
    today = today or timezone.localdate()
    history = _history_rows(ward, today - timedelta(days=30), today - timedelta(days=1))
    forecast = _forecast_rows(ward, today, today + timedelta(days=13))
    water_needs = crop.water_needs.lower()
    high_water_crop = "high" in water_needs
    planting_rain_threshold = 20 if high_water_crop else PLANTING_RAIN_MM
    recommended_forecast_threshold = 20 if high_water_crop else RECOMMENDED_FORECAST_MM
    very_dry_forecast_threshold = 30 if high_water_crop else VERY_DRY_FORECAST_MM
    historical_rain = sum(snapshot.rain_mm for snapshot in history)
    forecast_next_7 = sum(
        snapshot.rain_mm for snapshot in forecast if snapshot.date < today + timedelta(days=7)
    )
    forecast_total = sum(snapshot.rain_mm for snapshot in forecast)
    upcoming_rain_day = None
    for index, snapshot in enumerate(forecast):
        if snapshot.rain_mm >= planting_rain_threshold:
            upcoming_rain_day = snapshot
            break
        rain_window = forecast[index : index + 3]
        if (
            len(rain_window) == 3
            and (rain_window[-1].date - rain_window[0].date).days == 2
            and sum(day.rain_mm for day in rain_window) >= planting_rain_threshold
        ):
            upcoming_rain_day = next(
                (day for day in rain_window if day.rain_mm > 0),
                None,
            )
            if upcoming_rain_day:
                break

    if (
        historical_rain < VERY_DRY_HISTORY_MM
        and forecast_total < very_dry_forecast_threshold
    ):
        status = "TOO_DRY"
        reason = (
            f"{ward.name} has had only {historical_rain:.0f} mm of rain in the last 30 days "
            f"and {forecast_total:.0f} mm is forecast over the next 14 days. Wait for reliable rain."
        )
        wait_days = None
    elif (
        historical_rain >= RECOMMENDED_HISTORY_MM
        or forecast_next_7 >= recommended_forecast_threshold
    ):
        status = "RECOMMENDED_NOW"
        reason = (
            f"Rain conditions are suitable for planting {crop.name} in {ward.name}: "
            f"{historical_rain:.0f} mm fell in the last 30 days and "
            f"{forecast_next_7:.0f} mm is forecast in the next 7 days."
        )
        wait_days = 0
    elif upcoming_rain_day:
        wait_days = max(1, (upcoming_rain_day.date - today).days)
        status = f"WAIT_{wait_days}_DAYS"
        reason = (
            f"Wait {wait_days} days before planting {crop.name}; useful rain is expected "
            f"around {upcoming_rain_day.date.isoformat()} in {ward.name}."
        )
    else:
        status = "TOO_DRY"
        reason = (
            f"Rain is not reliable enough for planting {crop.name} in {ward.name}. "
            "Check the forecast again in a few days."
        )
        wait_days = None

    return {
        "status": status,
        "wait_days": wait_days,
        "reason": reason,
        "crop": crop.name,
        "crop_water_needs": crop.water_needs,
        "ward": ward.name,
        "historical_rain_30d_mm": round(historical_rain, 1),
        "forecast_rain_14d_mm": round(forecast_total, 1),
        "forecast_rain_7d_mm": round(forecast_next_7, 1),
    }


def rain_alerts(ward, crop=None, today=None):
    today = today or timezone.localdate()
    forecast = _forecast_rows(ward, today, today + timedelta(days=13))
    alerts = []

    rainfall = []
    for snapshot in forecast:
        hours = snapshot.forecast_json.get("hourly", [])
        rainfall.extend(
            (hour.get("time", ""), float(hour["precipitation"]))
            for hour in hours
            if hour.get("precipitation") is not None and hour.get("time")
        )
    heavy_period = _heaviest_24_hour_period(rainfall)
    if heavy_period and heavy_period["rain_mm"] > 25:
        alerts.append(
            _alert(
                "HEAVY_RAIN",
                "HIGH",
                datetime.fromisoformat(heavy_period["start"]).date(),
                f"Heavy rain: about {heavy_period['rain_mm']:.0f} mm may fall in 24 hours. "
                "Protect seedlings and keep drains clear.",
                rain_mm=round(heavy_period["rain_mm"], 1),
            )
        )

    dry_run = []
    for snapshot in forecast:
        if dry_run and snapshot.date != dry_run[-1] + timedelta(days=1):
            if len(dry_run) >= 7:
                alerts.append(
                    _alert(
                        "DRY_SPELL",
                        "MEDIUM",
                        dry_run[0],
                        f"A dry spell of {len(dry_run)} days is forecast from "
                        f"{dry_run[0].isoformat()}. Save water and mulch crops.",
                        days=len(dry_run),
                    )
                )
            dry_run = []
        if snapshot.rain_mm < DRY_DAY_MM:
            dry_run.append(snapshot.date)
        else:
            if len(dry_run) >= 7:
                alerts.append(
                    _alert(
                        "DRY_SPELL",
                        "MEDIUM",
                        dry_run[0],
                        f"A dry spell of {len(dry_run)} days is forecast from "
                        f"{dry_run[0].isoformat()}. Save water and mulch crops.",
                        days=len(dry_run),
                    )
                )
            dry_run = []
    if len(dry_run) >= 7:
        alerts.append(
            _alert(
                "DRY_SPELL",
                "MEDIUM",
                dry_run[0],
                f"A dry spell of {len(dry_run)} days is forecast from "
                f"{dry_run[0].isoformat()}. Save water and mulch crops.",
                days=len(dry_run),
            )
        )

    for index in range(len(forecast) - 2):
        window = forecast[index : index + 3]
        if (
            len(window) != 3
            or (window[-1].date - window[0].date).days != 2
        ):
            continue
        wet_days = sum(snapshot.rain_mm >= 1 for snapshot in window)
        average_humidity = sum(snapshot.humidity for snapshot in window) / 3
        average_temperature = sum(
            (snapshot.temp_min + snapshot.temp_max) / 2 for snapshot in window
        ) / 3
        if wet_days >= 2 and average_humidity >= 85 and 15 <= average_temperature <= 25:
            alerts.append(
                _alert(
                    "BLIGHT_CONDITIONS",
                    "HIGH",
                    window[0].date,
                    "Cool, wet weather may favour crop blight. Inspect leaves and avoid overhead watering.",
                    crop=crop.name if crop else None,
                    humidity_percent=round(average_humidity),
                    temperature_c=round(average_temperature, 1),
                )
            )
            break

    for snapshot in forecast:
        if snapshot.temp_min <= 5:
            alerts.append(
                _alert(
                    "COLD_NIGHT",
                    "HIGH",
                    snapshot.date,
                    f"Cold night expected ({snapshot.temp_min:.0f}°C). Protect flowers and other "
                    "sensitive plants from cold.",
                    min_temperature_c=snapshot.temp_min,
                    applies_to="flowers",
                )
            )

    return alerts


def _heaviest_24_hour_period(rainfall):
    if len(rainfall) < 24:
        return None
    heaviest = None
    for index in range(len(rainfall) - 23):
        window = rainfall[index : index + 24]
        if any(
            (datetime.fromisoformat(window[i + 1][0]) - datetime.fromisoformat(window[i][0]))
            != timedelta(hours=1)
            for i in range(len(window) - 1)
        ):
            continue
        amount = sum(rain for _, rain in window)
        if heaviest is None or amount > heaviest["rain_mm"]:
            heaviest = {"start": window[0][0], "rain_mm": amount}
    return heaviest


def _alert(code, severity, day, message, **details):
    return {
        "code": code,
        "severity": severity,
        "date": day.isoformat(),
        "message": message,
        **details,
    }


def sms_versions(status, wait_days=0):
    if status == "RECOMMENDED_NOW":
        parts = {
            "en": "Rain is suitable. Plant now; mulch and check drainage.",
            "sw": "Mvua inafaa. Panda sasa; tandaza na hakikisha mifereji iko wazi.",
            "guz": "[Guz translation placeholder] Plant now; rain is suitable.",
        }
    elif status.startswith("WAIT_"):
        parts = {
            "en": f"Wait {wait_days} days for rain, then plant. Check the forecast.",
            "sw": f"Subiri siku {wait_days} mvua inyeshe, kisha panda.",
            "guz": f"[Guz translation placeholder] Wait {wait_days} days, then plant.",
        }
    else:
        parts = {
            "en": "It is too dry to plant safely. Save water and check again soon.",
            "sw": "Kuna ukame. Usipande bado; hifadhi maji na uangalie tena.",
            "guz": "[Guz translation placeholder] Too dry to plant safely; check again soon.",
        }
    return {language: message[:159] for language, message in parts.items()}


def calendar_plan(crop, planting, window, forecast, today=None):
    today = today or timezone.localdate()
    planting_day = (
        planting.planted_on
        if planting
        else today + timedelta(days=window["wait_days"] or 0)
    )
    harvest_day = planting.expected_harvest if planting else None
    estimated_harvest = harvest_day or (
        planting_day + timedelta(days=120)
        if window["status"] != "TOO_DRY"
        else None
    )
    harvest_day = harvest_day or estimated_harvest
    weeks = []
    week_count = max(
        8,
        min(
            52,
            ((estimated_harvest - today).days + 6) // 7 + 1
            if estimated_harvest
            else 8,
        ),
    )
    for week_index in range(week_count):
        start = today + timedelta(days=week_index * 7)
        end = start + timedelta(days=6)
        actions = []
        categories = {
            "plant": [],
            "weed": [],
            "top_dress": [],
            "spray_window": [],
            "harvest": [],
        }

        def add_action(category, day, description):
            action = _calendar_action(category, day, description)
            categories[category].append(action)
            actions.append(action)

        if (
            not planting
            and week_index == 0
            and window["status"] == "RECOMMENDED_NOW"
        ):
            add_action("plant", planting_day, f"Plant {crop.name}")
        if (
            not planting
            and window["status"].startswith("WAIT_")
            and start <= planting_day <= end
        ):
            add_action("plant", planting_day, f"Plant {crop.name} after rain")
        weed_day = planting_day + timedelta(days=14)
        if (planting or window["status"] != "TOO_DRY") and start <= weed_day <= end:
            add_action("weed", weed_day, "Weed and check young crops")
        topdress_day = planting_day + timedelta(days=28)
        if (planting or window["status"] != "TOO_DRY") and start <= topdress_day <= end:
            add_action("top_dress", topdress_day, "Top-dress if soil is moist")
        if (
            (planting or window["status"] != "TOO_DRY")
            and end >= planting_day
            and (harvest_day is None or start + timedelta(days=2) < harvest_day)
        ):
            dry_forecast = next(
                (
                    snapshot
                    for snapshot in forecast
                    if max(start, planting_day) <= snapshot.date <= end
                    and snapshot.rain_mm < DRY_DAY_MM
                ),
                None,
            )
            if dry_forecast:
                add_action(
                    "spray_window",
                    dry_forecast.date,
                    "Inspect for pests; use this dry window only if spraying is needed",
                )
            elif not any(start <= snapshot.date <= end for snapshot in forecast):
                add_action(
                    "spray_window",
                    start + timedelta(days=2),
                    "Check the updated forecast and choose a dry day before spraying",
                )
        harvest_window_start = harvest_day - timedelta(days=7) if harvest_day else None
        if (
            harvest_day
            and end >= harvest_window_start
            and start <= harvest_day
        ):
            add_action(
                "harvest",
                max(start, harvest_window_start),
                "Check crop maturity and prepare to harvest",
            )
        weeks.append({
            "week": week_index + 1,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "actions": actions,
            **categories,
        })
    return {
        "crop": crop.name,
        "planting_date": (
            planting_day.isoformat()
            if planting or window["status"] != "TOO_DRY"
            else None
        ),
        "estimated_harvest": estimated_harvest.isoformat(),
        "weeks": weeks,
    }


def _calendar_action(action, day, description):
    return {"type": action, "date": day.isoformat(), "description": description}


def planner_for_farm(farm, today=None):
    today = today or timezone.localdate()
    planting = farm.plantings.select_related("crop").order_by("-planted_on").first()
    crop = planting.crop if planting else None
    if crop is None:
        from farms.models import Crop

        crop = Crop.objects.order_by("name").first()
    if crop is None:
        return {
            "planting_window": None,
            "rain_alerts": [],
            "calendar": {
                "crop": None,
                "planting_date": None,
                "estimated_harvest": None,
                "weeks": [],
            },
            "sms": {},
            "notice": "Add a crop reference to generate a planting plan.",
        }

    window = planting_window(crop, farm.farmer.ward, today=today)
    alerts = rain_alerts(farm.farmer.ward, crop=crop, today=today)
    forecast = _forecast_rows(farm.farmer.ward, today, today + timedelta(days=13))
    return {
        "planting_window": window,
        "rain_alerts": alerts,
        "calendar": calendar_plan(crop, planting, window, forecast, today=today),
        "sms": sms_versions(window["status"], window["wait_days"] or 0),
    }
