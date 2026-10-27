import logging
import math
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from alerts.models import Alert, AlertDelivery, Rule, RuleWardPriority
from farms.models import Farm
from market.models import MarketPrice
from pests.models import PestReport, SprayLog
from waste.models import WasteLog

logger = logging.getLogger(__name__)

RULE_DEFAULTS = {
    "HEAVY_RAIN_STEEP": {
        "problem_tag": "erosion",
        "severity": Rule.Severity.HIGH,
        "threshold": 25,
        "title": "Heavy rain and erosion risk",
        "messages": {
            "en": "More than {rain_mm:.0f} mm rain is forecast. Your steep farm may erode; protect soil and clear safe drainage.",
            "sw": "Mvua kubwa ya {rain_mm:.0f} mm inatarajiwa. Linda udongo kwenye shamba lenye mteremko.",
            "guz": "[Guz translation placeholder] Heavy rain may wash soil from your steep farm.",
        },
    },
    "COOL_WET_TOMATO_BLIGHT": {
        "problem_tag": "pests",
        "severity": Rule.Severity.HIGH,
        "temperature": 20,
        "humidity": 85,
        "days": 2,
        "title": "Tomato blight conditions",
        "messages": {
            "en": "Cool, humid weather may cause tomato blight. Inspect leaves and avoid wetting them.",
            "sw": "Hali ya baridi na unyevu inaweza kusababisha blight kwenye nyanya. Kagua majani.",
            "guz": "[Guz translation placeholder] Cool wet weather may cause tomato blight; inspect leaves.",
        },
    },
    "OUTBREAK_NEARBY": {
        "problem_tag": "pests",
        "severity": Rule.Severity.HIGH,
        "count": 3,
        "days": 7,
        "title": "Pest outbreak reported nearby",
        "messages": {
            "en": "{count} confirmed {pest_name} reports were recorded in your ward. Inspect crops and report new cases.",
            "sw": "Kesi {count} zilizothibitishwa za {pest_name} zimeripotiwa katika kata yako. Kagua mimea.",
            "guz": "[Guz translation placeholder] {count} confirmed {pest_name} reports in your ward; inspect crops.",
        },
    },
    "SPRAY_LOGGED": {
        "problem_tag": "ppe",
        "severity": Rule.Severity.MEDIUM,
        "title": "Spray safety reminder",
        "messages": {
            "en": "After spraying {product_name}: use PPE, wait {reentry_hours} hours before re-entry, and wait {pre_harvest_days} days before harvest.",
            "sw": "Baada ya kunyunyiza {product_name}: vaa PPE, subiri saa {reentry_hours} kabla ya kuingia na siku {pre_harvest_days} kabla ya kuvuna.",
            "guz": "[Guz translation placeholder] After {product_name}, use PPE; wait {reentry_hours} hours to enter and {pre_harvest_days} days to harvest.",
        },
    },
    "LOW_PH": {
        "problem_tag": "soil",
        "severity": Rule.Severity.LOW,
        "title": "Soil may need lime",
        "messages": {
            "en": "Soil pH {soil_ph:.1f} is below {crop_name}'s preferred range. Ask an officer about a soil test and lime rate.",
            "sw": "pH ya udongo {soil_ph:.1f} iko chini kwa {crop_name}. Uliza afisa kuhusu kipimo na chokaa.",
            "guz": "[Guz translation placeholder] Soil pH is low for {crop_name}; ask an officer about a soil test and lime.",
        },
    },
    "DRY_SPELL_MULCH": {
        "problem_tag": "climate",
        "severity": Rule.Severity.MEDIUM,
        "days": 7,
        "title": "Dry spell: conserve soil moisture",
        "messages": {
            "en": "A dry spell of {days} days is forecast. Mulch around crops and irrigate early if water is available.",
            "sw": "Kiangazi cha siku {days} kinatarajiwa. Weka matandazo na mwagilia mapema ikiwa maji yapo.",
            "guz": "[Guz translation placeholder] A {days}-day dry spell is expected; mulch crops and irrigate early.",
        },
    },
    "PRICE_SPIKE": {
        "problem_tag": "market",
        "severity": Rule.Severity.MEDIUM,
        "increase_percent": 20,
        "title": "Good selling price nearby",
        "messages": {
            "en": "{crop_name} is selling at {price} per kg at {market_name}, {increase_percent:.0f}% above its 4-week average.",
            "sw": "{crop_name} inauzwa {price} kwa kilo {market_name}, juu kwa {increase_percent:.0f}% ya wastani wa wiki 4.",
            "guz": "[Guz translation placeholder] {crop_name} is {increase_percent:.0f}% above its 4-week average at {market_name}.",
        },
    },
    "WASTE_REMINDER": {
        "problem_tag": "waste",
        "severity": Rule.Severity.LOW,
        "days": 7,
        "title": "Safe chemical container disposal",
        "messages": {
            "en": "It has been 7 days since spraying {product_name}. Triple-rinse the container and take it to an approved drop-off point.",
            "sw": "Siku 7 tangu unyunyize {product_name}. Suuza chombo mara tatu na upeleke kituo kilichoidhinishwa.",
            "guz": "[Guz translation placeholder] Triple-rinse the {product_name} container and take it to an approved drop-off point.",
        },
    },
}


def _condition_value(value, default):
    if isinstance(value, dict):
        for operator in (
            "over",
            "above",
            "gt",
            "min",
            "under",
            "below",
            "lt",
            "max",
            "days",
            "equals",
        ):
            if operator in value:
                return value[operator]
        return default
    return value if value is not None else default


def _condition(rule, key, default, *aliases):
    if rule is None:
        return default
    for candidate in (key, *aliases):
        if candidate in rule.condition_json:
            return _condition_value(rule.condition_json[candidate], default)
    return default


def _render(rule, values):
    defaults = RULE_DEFAULTS[rule.code]
    configured = rule.message_templates or {}
    body = {}
    for language in ("en", "sw", "guz"):
        template = configured.get(language)
        if isinstance(template, dict):
            template = template.get("body", template.get("message"))
        if not isinstance(template, str):
            template = defaults["messages"][language]
        try:
            body[language] = template.format(**values)
        except (KeyError, ValueError, TypeError):
            logger.exception("Invalid message template for alert rule %s (%s).", rule.code, language)
            body[language] = defaults["messages"][language].format(**values)
    return body


def _effective_priority(rule, ward):
    try:
        return rule.ward_priorities.get(ward=ward).priority
    except RuleWardPriority.DoesNotExist:
        return 100


def _effective_severity(rule, priority):
    rank = {
        Rule.Severity.LOW: 0,
        Rule.Severity.MEDIUM: 1,
        Rule.Severity.HIGH: 2,
        Rule.Severity.CRITICAL: 3,
    }
    severity_order = [
        Rule.Severity.LOW,
        Rule.Severity.MEDIUM,
        Rule.Severity.HIGH,
        Rule.Severity.CRITICAL,
    ]
    reduction = max(0, min(2, (100 - priority) // 30))
    return severity_order[max(0, rank[rule.severity] - reduction)]


def _create_alert(rule, farmer, farm, values, source_key, urgent=False):
    if not rule.active:
        return None
    now = timezone.now()
    if source_key:
        existing = Alert.objects.filter(
            farmer=farmer,
            rule=rule,
            source_key=source_key,
        ).first()
        if existing:
            return None
    if rule.cooldown_hours:
        recent = Alert.objects.filter(
            farmer=farmer,
            farm=farm,
            rule=rule,
            created_at__gte=now - timedelta(hours=rule.cooldown_hours),
        ).exists()
        if recent:
            return None

    priority = _effective_priority(rule, farmer.ward)
    severity = _effective_severity(rule, priority)
    if urgent:
        severity = max(
            (severity, Rule.Severity.HIGH),
            key={
                Rule.Severity.LOW: 0,
                Rule.Severity.MEDIUM: 1,
                Rule.Severity.HIGH: 2,
                Rule.Severity.CRITICAL: 3,
            }.get,
        )
    try:
        with transaction.atomic():
            alert = Alert.objects.create(
                farmer=farmer,
                farm=farm,
                rule=rule,
                severity=severity,
                priority=priority,
                title=RULE_DEFAULTS[rule.code]["title"],
                body_by_language=_render(rule, values),
                source_key=source_key or "",
            )
    except IntegrityError:
        if source_key:
            return None
        raise
    return alert


def _rule_by_code(code):
    return Rule.objects.filter(code=code, active=True).first()


def _create_for_farm(code, farm, values, source_key, urgent=False):
    rule = _rule_by_code(code)
    if not rule:
        return []
    alert = _create_alert(
        rule,
        farm.farmer,
        farm,
        values,
        source_key,
        urgent=urgent,
    )
    return [alert] if alert else []


def _forecast(farm, start, end):
    from weather.models import WeatherSnapshot

    return list(
        WeatherSnapshot.objects.filter(
            ward=farm.farmer.ward,
            date__gte=start,
            date__lte=end,
            forecast_json__is_forecast=True,
        ).order_by("date")
    )


def _heavy_rain_24h(forecast):
    rainfall = []
    for snapshot in forecast:
        rainfall.extend(
            (hour.get("time", ""), float(hour["precipitation"]))
            for hour in snapshot.forecast_json.get("hourly", [])
            if hour.get("time") and hour.get("precipitation") is not None
        )
    rainfall.sort(key=lambda record: record[0])
    best = None
    for start in range(max(0, len(rainfall) - 23)):
        period = rainfall[start : start + 24]
        if len(period) != 24:
            continue
        from datetime import datetime

        times = [datetime.fromisoformat(record[0]) for record in period]
        if any(times[i + 1] - times[i] != timedelta(hours=1) for i in range(23)):
            continue
        total = sum(record[1] for record in period)
        if best is None or total > best["rain_mm"]:
            best = {"rain_mm": total, "date": times[0].date()}
    return best


def _dry_spells(forecast, minimum_days):
    spells = []
    run = []
    for snapshot in forecast:
        if run and snapshot.date != run[-1].date + timedelta(days=1):
            if len(run) >= minimum_days:
                spells.append(run)
            run = []
        if snapshot.rain_mm < 1:
            run.append(snapshot)
        else:
            if len(run) >= minimum_days:
                spells.append(run)
            run = []
    if len(run) >= minimum_days:
        spells.append(run)
    return spells


def _evaluate_farm(farm, now):
    today = timezone.localdate(now)
    alerts = []
    forecast = _forecast(farm, today, today + timedelta(days=13))
    heavy_rule = _rule_by_code("HEAVY_RAIN_STEEP")
    heavy_threshold = (
        float(_condition(heavy_rule, "rain_forecast_24h", 25))
        if heavy_rule
        else 25
    )
    farm_conditions = heavy_rule.condition_json.get("farm", {}) if heavy_rule else {}
    slope_class = _condition(
        heavy_rule,
        "slope_class",
        farm_conditions.get("slope_class", Farm.SlopeClass.STEEP),
    )
    heavy = _heavy_rain_24h(forecast)
    if farm.slope_class == slope_class and heavy and heavy["rain_mm"] > heavy_threshold:
        alerts += _create_for_farm(
            "HEAVY_RAIN_STEEP",
            farm,
            {"rain_mm": heavy["rain_mm"]},
            f"heavy-rain:{heavy['date'].isoformat()}",
            urgent=True,
        )

    blight_rule = _rule_by_code("COOL_WET_TOMATO_BLIGHT")
    blight_conditions = blight_rule.condition_json if blight_rule else {}
    planting_conditions = blight_conditions.get("planting", {})
    expected_crop = _condition(
        blight_rule,
        "crop",
        planting_conditions.get("crop", "tomato"),
    )
    tomato_plantings = [
        planting
        for planting in farm.plantings.select_related("crop").all()
        if _crop_matches(planting.crop.name, str(expected_crop))
    ]
    if blight_rule:
        temp_limit = float(_condition(blight_rule, "temp", 20))
        humidity_limit = float(_condition(blight_rule, "humidity", 85))
        wet_days = int(_condition(blight_rule, "days", 2))
        for planting in tomato_plantings:
            for index in range(len(forecast) - wet_days + 1):
                period = forecast[index : index + wet_days]
                if (
                    len(period) == wet_days
                    and all(
                        period[offset].date
                        == period[offset - 1].date + timedelta(days=1)
                        for offset in range(1, len(period))
                    )
                    and all(
                        snapshot.temp_min < temp_limit
                        and snapshot.humidity > humidity_limit
                        for snapshot in period
                    )
                ):
                    alerts += _create_for_farm(
                        "COOL_WET_TOMATO_BLIGHT",
                        farm,
                        {"crop_name": planting.crop.name},
                        f"blight:{planting.pk}:{period[0].date.isoformat()}",
                        urgent=True,
                    )
                    break

    dry_rule = _rule_by_code("DRY_SPELL_MULCH")
    if dry_rule:
        minimum_days = int(
            _condition(dry_rule, "days", 7, "consecutive_dry_days", "dry_days")
        )
        spells = _dry_spells(forecast, minimum_days)
        if spells:
            spell = spells[0]
            alerts += _create_for_farm(
                "DRY_SPELL_MULCH",
                farm,
                {"days": len(spell)},
                f"dry-spell:{spell[0].date.isoformat()}",
            )

    ph_rule = _rule_by_code("LOW_PH")
    if ph_rule and farm.soil_ph is not None:
        plantings = list(farm.plantings.select_related("crop").all())
        low_planting = next(
            (planting for planting in plantings if farm.soil_ph < planting.crop.ideal_ph_min),
            None,
        )
        if low_planting:
            alerts += _create_for_farm(
                "LOW_PH",
                farm,
                {
                    "soil_ph": farm.soil_ph,
                    "crop_name": low_planting.crop.name,
                    "ideal_ph_min": low_planting.crop.ideal_ph_min,
                },
                f"low-ph:{farm.pk}:{low_planting.crop_id}:{farm.soil_ph}",
            )

    price_rule = _rule_by_code("PRICE_SPIKE")
    if price_rule:
        alerts += _evaluate_price_spike(farm, price_rule, today)
    return alerts


def _evaluate_price_spike(farm, rule, today):
    alerts = []
    increase = float(
        _condition(rule, "increase_percent", 20, "percent_above_average")
    )
    all_prices = MarketPrice.objects.filter(
        date__gte=today - timedelta(days=28),
        date__lte=today,
    ).select_related("crop", "ward")
    for planting in farm.plantings.select_related("crop").all():
        crop_prices = list(all_prices.filter(crop=planting.crop).order_by("-date"))
        if not crop_prices:
            continue
        nearest_ward = min(
            (price.ward for price in crop_prices),
            key=lambda ward: _distance_km(farm.lat, farm.lng, ward.lat, ward.lng),
        )
        nearest_prices = [price for price in crop_prices if price.ward_id == nearest_ward.pk]
        market_names = {price.market_name for price in nearest_prices}
        candidates = []
        for market_name in market_names:
            market_prices = [
                price for price in nearest_prices if price.market_name == market_name
            ]
            latest = max(market_prices, key=lambda price: (price.date, price.pk))
            historical = [price for price in market_prices if price.date < latest.date]
            if not historical:
                continue
            average = sum(
                float(price.price_per_kg) for price in historical
            ) / len(historical)
            if average <= 0:
                continue
            percent = (float(latest.price_per_kg) - average) / average * 100
            if percent >= increase:
                candidates.append((latest.date, percent, latest))
        if not candidates:
            continue
        _, nearest_percent, nearest_latest = max(
            candidates, key=lambda candidate: (candidate[0], candidate[1])
        )
        alerts += _create_for_farm(
            "PRICE_SPIKE",
            farm,
            {
                "crop_name": planting.crop.name,
                "price": nearest_latest.price_per_kg,
                "market_name": nearest_latest.market_name,
                "increase_percent": nearest_percent,
            },
            f"price-spike:{planting.pk}:{nearest_latest.pk}",
        )
    return alerts


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _crop_matches(crop_name, expected):
    return expected.casefold() in crop_name.casefold()


def _evaluate_outbreaks(now):
    from pests.services import update_outbreak_for_report

    report_ids = (
        PestReport.objects.filter(
            status=PestReport.Status.CONFIRMED,
            created_at__gte=now - timedelta(days=7),
        )
        .order_by()
        .values_list("pk", flat=True)
    )
    alerts_before = set(
        Alert.objects.filter(rule__code="OUTBREAK_NEARBY")
        .values_list("pk", flat=True)
    )
    for report in PestReport.objects.filter(pk__in=report_ids).select_related(
        "ward", "crop"
    ):
        update_outbreak_for_report(report, now=now)
    return list(
        Alert.objects.filter(rule__code="OUTBREAK_NEARBY")
        .exclude(pk__in=alerts_before)
    )


def _evaluate_waste_reminders(now):
    rule = _rule_by_code("WASTE_REMINDER")
    if not rule:
        return []
    days = int(_condition(rule, "days", 7))
    due_before = now - timedelta(days=days)
    spray_logs = SprayLog.objects.filter(sprayed_at__lte=due_before).select_related(
        "farm__farmer__ward", "farm__farmer__user"
    )
    alerts = []
    for spray in spray_logs:
        if WasteLog.objects.filter(
            farmer=spray.farm.farmer,
            spray_log=spray,
            logged_at__gte=spray.sprayed_at,
        ).exists():
            continue
        alerts += _create_for_farm(
            "WASTE_REMINDER",
            spray.farm,
            {"product_name": spray.product_name},
            f"waste-reminder:spray:{spray.pk}",
        )
    return alerts


def evaluate_spray_log(spray):
    rule = _rule_by_code("SPRAY_LOGGED")
    if not rule:
        return []
    return _create_for_farm(
        "SPRAY_LOGGED",
        spray.farm,
        {
            "product_name": spray.product_name,
            "reentry_hours": spray.reentry_hours,
            "pre_harvest_days": spray.pre_harvest_days,
        },
        f"spray-log:{spray.pk}",
    )


def evaluate_rules(now=None):
    now = now or timezone.now()
    created = []
    for farm in Farm.objects.select_related("farmer__ward", "farmer__user").iterator():
        created.extend(_evaluate_farm(farm, now))
    created.extend(_evaluate_outbreaks(now))
    created.extend(_evaluate_waste_reminders(now))
    return created


def record_rule_feedback(delivery):
    if delivery.feedback != AlertDelivery.Feedback.NOT_RELEVANT or not delivery.alert.rule_id:
        return
    ward = delivery.alert.farmer.ward
    negative_count = (
        AlertDelivery.objects.filter(
            alert__rule=delivery.alert.rule,
            alert__farmer__ward=ward,
            feedback=AlertDelivery.Feedback.NOT_RELEVANT,
        )
        .values("alert_id")
        .distinct()
        .count()
    )
    if negative_count < 3:
        return
    priority = max(20, 100 - 10 * (negative_count - 2))
    RuleWardPriority.objects.update_or_create(
        rule=delivery.alert.rule,
        ward=ward,
        defaults={"priority": priority},
    )


def priority_for_rule(rule, ward):
    return _effective_priority(rule, ward)
