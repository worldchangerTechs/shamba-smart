from datetime import timedelta
from math import atan2, cos, isfinite, radians, sin, sqrt

from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import User
from advice.models import AdviceContent, PpeSupplier
from farms.models import Crop, Farm
from weather.models import WeatherSnapshot
from waste.models import DisposalPoint, WasteLog

PPE_ITEM_CODES = ("mask", "gloves", "boots", "overall", "goggles")
EFFORT_ORDER = {
    AdviceContent.Effort.LOW: 0,
    AdviceContent.Effort.MEDIUM: 1,
    AdviceContent.Effort.HIGH: 2,
}


def localize_advice_content(content, language):
    return {
        "code": content.code,
        "title": getattr(content, f"title_{language}") or content.title_en,
        "body": getattr(content, f"body_{language}") or content.body_en,
        "title_by_language": {
            "en": content.title_en,
            "sw": content.title_sw,
            "guz": content.title_guz,
        },
        "body_by_language": {
            "en": content.body_en,
            "sw": content.body_sw,
            "guz": content.body_guz,
        },
        "cost_kes_per_acre": (
            {
                "min": content.cost_min_kes_per_acre,
                "max": content.cost_max_kes_per_acre,
            }
            if content.cost_min_kes_per_acre is not None
            else None
        ),
        "effort": content.effort,
        "metadata": content.metadata,
    }


def _advice(code, language):
    content = AdviceContent.objects.get(code=code, active=True)
    return localize_advice_content(content, language)


def get_farm_for_user(user, farm_id):
    farms = Farm.objects.select_related("farmer__ward", "farmer__user")
    if user.is_superuser or user.role == User.Role.ADMIN:
        return get_object_or_404(farms, pk=farm_id)
    if user.role == User.Role.FARMER:
        return get_object_or_404(farms, pk=farm_id, farmer__user=user)
    if user.role == User.Role.OFFICER:
        return get_object_or_404(
            farms, pk=farm_id, farmer__ward__in=user.assigned_wards.all()
        )
    return get_object_or_404(farms.none(), pk=farm_id)


def udongo_doctor(*, crop_name, soil_ph=None, quiz=None, language="en"):
    crop = get_object_or_404(Crop, name__iexact=crop_name)
    quiz = quiz or {}
    fertility_signals = 0
    if quiz:
        fertility_signals += quiz["leaf_colour"] in {"pale", "yellow"}
        fertility_signals += quiz["soil_colour"] == "pale"
        fertility_signals += quiz["past_yields"] == "falling"
        fertility_signals += quiz["rain_washing"] == "yes"
        fertility_signals += quiz["mulch_use"] == "no"
        fertility_signals += quiz["manure_use"] == "no"

    low_ph = soil_ph is not None and soil_ph < crop.ideal_ph_min
    needs_organic_matter = fertility_signals >= 2
    content = AdviceContent.objects.filter(service=AdviceContent.Service.UDONGO, active=True)
    selected_codes = {
        "TOP_DRESS",
        "CROP_ROTATION",
        "LEGUMES",
        "FERTILISER_WARNING",
    }
    if low_ph:
        selected_codes.add("LIME_LOW_PH")
    selected_codes.add("COMPOST")
    if needs_organic_matter:
        selected_codes.add("MANURE")

    tasks = [
        localize_advice_content(item, language)
        for item in content.filter(code__in=selected_codes)
    ]
    priority = {
        "LIME_LOW_PH": 0,
        "COMPOST": 1,
        "MANURE": 2,
        "TOP_DRESS": 3,
        "CROP_ROTATION": 4,
        "LEGUMES": 5,
        "FERTILISER_WARNING": 6,
    }
    tasks.sort(key=lambda task: priority[task["code"]])
    summary_by_language = AdviceContent.objects.get(
        code="FERTILISER_WARNING", active=True
    ).metadata.get("summary_by_language", {})
    summary = (
        summary_by_language.get(language)
        or summary_by_language.get("en", "Improve soil gradually and protect it.")
    )
    return {
        "crop": {"name": crop.name, "ideal_ph_min": crop.ideal_ph_min},
        "soil_ph": soil_ph,
        "visual_fertility_signals": fertility_signals,
        "summary": summary,
        "warning": _advice("FERTILISER_WARNING", language),
        "tasks": tasks,
    }


def mteremko_guard(*, farm, ground_cover_percent, tillage, language="en", today=None):
    today = today or timezone.localdate()
    rain = WeatherSnapshot.objects.filter(
        ward=farm.farmer.ward,
        date__gte=today,
        date__lte=today + timedelta(days=13),
        forecast_json__is_forecast=True,
    ).values_list("rain_mm", flat=True)
    rain_values = list(rain)
    rain_total = sum(rain_values)
    slope_score = {
        Farm.SlopeClass.FLAT: 8,
        Farm.SlopeClass.GENTLE: 28,
        Farm.SlopeClass.STEEP: 52,
    }[farm.slope_class]
    rain_score = min(32, int(rain_total * 0.2))
    if rain_values and max(rain_values) >= 25:
        rain_score += 10
    cover_reduction = int(ground_cover_percent * 0.25)
    tillage_score = {"upslope": 20, "conventional": 8, "contour": -10}[tillage]
    risk_score = max(
        0, min(100, slope_score + rain_score - cover_reduction + tillage_score)
    )
    controls = [
        localize_advice_content(item, language)
        for item in AdviceContent.objects.filter(
            service=AdviceContent.Service.MTEREMKO, active=True
        )
    ]
    controls.sort(
        key=lambda item: (
            item["cost_kes_per_acre"]["min"]
            if item["cost_kes_per_acre"]
            else 0,
            EFFORT_ORDER.get(item["effort"], 0),
            item["code"],
        )
    )
    calendar = _advice("NAPIER_VETIVER", language)["metadata"].get(
        "seasonal_calendar", {}
    )
    return {
        "farm_id": farm.pk,
        "risk_score": risk_score,
        "risk_level": "HIGH" if risk_score >= 70 else "MODERATE" if risk_score >= 40 else "LOW",
        "inputs": {
            "slope_class": farm.slope_class,
            "forecast_rain_14d_mm": round(rain_total, 1),
            "ground_cover_percent": ground_cover_percent,
            "tillage": tillage,
        },
        "controls": controls,
        "seasonal_erosion_calendar": calendar,
    }


def haversine_km(lat1, lng1, lat2, lng2):
    radius_km = 6371
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lng / 2) ** 2
    )
    return radius_km * 2 * atan2(sqrt(value), sqrt(1 - value))


def taka_loop(*, farmer, waste_type, farm=None, language="en"):
    code = {
        "CROP_RESIDUE": "COMPOST_CROP_RESIDUE",
        "CHEMICAL_CONTAINER": "PESTICIDE_TRIPLE_RINSE",
        "PACKAGING": "NEVER_BURN_PLASTIC",
    }[waste_type]
    recipe = _advice(code, language)
    location = farm or farmer.farms.order_by("pk").first()
    if location:
        lat, lng = location.lat, location.lng
    else:
        lat, lng = farmer.ward.lat, farmer.ward.lng
    disposal_points = list(
        DisposalPoint.objects.select_related("ward").all()
    )
    nearest = min(
        disposal_points,
        key=lambda point: haversine_km(lat, lng, point.lat, point.lng),
        default=None,
    )
    nearest_data = None
    if nearest:
        nearest_data = {
            "id": nearest.pk,
            "name": nearest.name,
            "type": nearest.type,
            "lat": nearest.lat,
            "lng": nearest.lng,
            "ward": nearest.ward.name,
            "hours": nearest.hours,
            "contact": nearest.contact,
            "distance_km": round(
                haversine_km(lat, lng, nearest.lat, nearest.lng), 2
            ),
        }
    action_count = WasteLog.objects.filter(farmer=farmer).count()
    return {
        "waste_type": waste_type,
        "recipe": recipe,
        "nearest_disposal_point": nearest_data,
        "clean_farm": {
            "waste_action_count": action_count,
            "score": min(100, action_count * 10),
            "score_per_logged_action": 10,
        },
    }


def ppe_gap_finder(*, farmer, owned_items, farm=None, language="en"):
    missing = [code for code in PPE_ITEM_CODES if code not in set(owned_items)]
    if farm:
        lat, lng = farm.lat, farm.lng
    else:
        lat, lng = farmer.ward.lat, farmer.ward.lng

    suppliers = list(PpeSupplier.objects.filter(active=True).select_related("ward"))
    content = AdviceContent.objects.get(
        code="PPE_CHECKLIST", active=True
    )
    item_labels = content.metadata.get("ppe_items", {})
    cheapest_items = []
    for code in missing:
        offers = []
        for supplier in suppliers:
            price = supplier.item_prices_kes.get(code)
            if price is None:
                continue
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if not isfinite(price) or price < 0:
                continue
            offers.append((price, supplier))
        if not offers:
            cheapest_items.append(
                {
                    "code": code,
                    "name": item_labels.get(code, {}).get(language)
                    or item_labels.get(code, {}).get("en", code),
                    "lowest_price_kes": None,
                    "supplier": None,
                }
            )
            continue
        price, supplier = min(offers, key=lambda offer: (offer[0], offer[1].pk))
        cheapest_items.append(
            {
                "code": code,
                "name": item_labels.get(code, {}).get(language)
                or item_labels.get(code, {}).get("en", code),
                "lowest_price_kes": price,
                "supplier": {
                    "id": supplier.pk,
                    "name": supplier.name,
                    "type": supplier.supplier_type,
                    "ward": supplier.ward.name,
                    "contact": supplier.contact,
                    "distance_km": round(
                        haversine_km(lat, lng, supplier.lat, supplier.lng), 2
                    ),
                },
            }
        )
    cheapest_items.sort(
        key=lambda item: (
            item["lowest_price_kes"] is None,
            item["lowest_price_kes"]
            if item["lowest_price_kes"] is not None
            else float("inf"),
            item["code"],
        )
    )
    available_suppliers = [
        supplier
        for supplier in suppliers
        if any(
            code in supplier.item_prices_kes
            and _valid_price(supplier.item_prices_kes[code])
            for code in missing
        )
    ]
    nearest = min(
        available_suppliers,
        key=lambda supplier: (
            haversine_km(lat, lng, supplier.lat, supplier.lng),
            supplier.pk,
        ),
        default=None,
    )
    nearest_data = None
    if nearest:
        nearest_data = {
            "id": nearest.pk,
            "name": nearest.name,
            "type": nearest.supplier_type,
            "ward": nearest.ward.name,
            "contact": nearest.contact,
            "distance_km": round(
                haversine_km(lat, lng, nearest.lat, nearest.lng), 2
            ),
            "available_items": [
                code
                for code in missing
                if code in nearest.item_prices_kes
                and _valid_price(nearest.item_prices_kes[code])
            ],
        }
    return {
        "owned_items": list(owned_items),
        "missing_items": cheapest_items,
        "nearest_supplier": nearest_data,
    }


def _valid_price(value):
    try:
        price = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(price) and price >= 0
