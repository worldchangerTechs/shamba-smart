from datetime import timedelta
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt

from django.db.models import Avg, Max
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import Ward
from farms.models import Crop, Farm
from market.models import MarketPrice


def haversine_km(lat1, lng1, lat2, lng2):
    radius_km = 6371
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(delta_lng / 2) ** 2
    )
    return radius_km * 2 * atan2(sqrt(value), sqrt(1 - value))


def _percent_change(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def crop_price_trends(*, crop, ward=None, market_name=None, today=None):
    today = today or timezone.localdate()
    prices = MarketPrice.objects.filter(
        crop=crop,
        date__gte=today - timedelta(days=59),
        date__lte=today,
    )
    if ward is not None:
        prices = prices.filter(ward=ward)
    if market_name:
        prices = prices.filter(market_name__iexact=market_name)

    daily = list(
        prices.values("date")
        .annotate(average=Avg("price_per_kg"))
        .order_by("date")
    )
    points_by_date = {point["date"]: point["average"] for point in daily}
    current_7 = [
        points_by_date[day]
        for day in (today - timedelta(days=offset) for offset in range(7))
        if day in points_by_date
    ]
    previous_7 = [
        points_by_date[day]
        for day in (
            today - timedelta(days=offset) for offset in range(7, 14)
        )
        if day in points_by_date
    ]
    current_30 = [
        points_by_date[day]
        for day in (today - timedelta(days=offset) for offset in range(30))
        if day in points_by_date
    ]
    previous_30 = [
        points_by_date[day]
        for day in (today - timedelta(days=offset) for offset in range(30, 60))
        if day in points_by_date
    ]
    average = lambda values: (
        sum(values, Decimal("0")) / len(values) if values else None
    )
    recent_prices = list(prices)
    return {
        "crop": {"id": crop.pk, "name": crop.name},
        "ward": {"id": ward.pk, "name": ward.name} if ward else None,
        "market_name": market_name,
        "currency": "KES",
        "unit": "kg",
        "trend_7d": {
            "daily_prices": [
                {"date": day.isoformat(), "average_price_per_kg": str(value)}
                for day, value in sorted(points_by_date.items())
                if day >= today - timedelta(days=6)
            ],
            "average_price_per_kg": str(average(current_7))
            if current_7
            else None,
            "previous_period_average_per_kg": str(average(previous_7))
            if previous_7
            else None,
            "change_percent": _percent_change(average(current_7), average(previous_7)),
        },
        "trend_30d": {
            "daily_prices": [
                {"date": day.isoformat(), "average_price_per_kg": str(value)}
                for day, value in sorted(points_by_date.items())
                if day >= today - timedelta(days=29)
            ],
            "average_price_per_kg": str(average(current_30))
            if current_30
            else None,
            "previous_period_average_per_kg": str(average(previous_30))
            if previous_30
            else None,
            "change_percent": _percent_change(average(current_30), average(previous_30)),
        },
        "is_sample_data": bool(recent_prices)
        and all(item.is_sample_data for item in recent_prices),
    }


def compare_local_price(*, farm, crop, middleman_price, quantity_kg, today=None):
    today = today or timezone.localdate()
    prices = list(
        MarketPrice.objects.filter(
            crop=crop,
            date__gte=today - timedelta(days=30),
            date__lte=today,
        )
        .select_related("ward")
        .order_by("-date")
    )
    latest_by_market = {}
    for price in prices:
        key = (price.market_name, price.ward_id)
        if key not in latest_by_market:
            latest_by_market[key] = price
    nearby = [
        (haversine_km(farm.lat, farm.lng, price.ward.lat, price.ward.lng), price)
        for price in latest_by_market.values()
    ]
    nearby = [
        (distance, price)
        for distance, price in nearby
        if distance <= 30
    ]
    if not nearby:
        return {
            "farm_id": farm.pk,
            "crop": crop.name,
            "radius_km": 30,
            "local_middleman_price_per_kg": str(middleman_price),
            "best_market": None,
            "estimated_gain": None,
            "message": "No recent market price is available within 30 km.",
        }
    distance, best = max(
        nearby,
        key=lambda item: (item[1].price_per_kg, item[1].date, -item[0]),
    )
    difference = best.price_per_kg - middleman_price
    gain = difference * quantity_kg
    return {
        "farm_id": farm.pk,
        "crop": crop.name,
        "radius_km": 30,
        "local_middleman_price_per_kg": str(middleman_price),
        "best_market": {
            "name": best.market_name,
            "ward": best.ward.name,
            "price_per_kg": str(best.price_per_kg),
            "date": best.date.isoformat(),
            "distance_km": round(distance, 2),
            "is_sample_data": best.is_sample_data,
        },
        "price_difference_per_kg": str(difference),
        "estimated_gain": {
            "currency": "KES",
            "quantity_kg": str(quantity_kg),
            "amount": str(gain.quantize(Decimal("0.01"))),
            "percent_above_middleman": round(
                float(difference / middleman_price * 100), 1
            )
            if middleman_price > 0
            else None,
            "note": "Estimate excludes transport, handling, and other selling costs.",
        },
    }


def public_price_lookup(*, crop_name, ward_name, language="en"):
    crop = get_object_or_404(
        Crop.objects.filter(
            Q(name__iexact=crop_name.strip())
            | Q(local_name_sw__iexact=crop_name.strip())
            | Q(local_name_guz__iexact=crop_name.strip())
        ).order_by("name")
    )
    ward = get_object_or_404(Ward, name__iexact=ward_name.strip())
    today = timezone.localdate()
    latest_date = MarketPrice.objects.filter(
        crop=crop, ward=ward, date__lte=today
    ).aggregate(latest=Max("date"))["latest"]
    if latest_date is None:
        return None
    prices = list(
        MarketPrice.objects.filter(
            crop=crop, ward=ward, date=latest_date
        ).order_by("price_per_kg", "market_name")
    )
    if not prices:
        return None
    average = sum(
        (price.price_per_kg for price in prices), Decimal("0")
    ) / len(prices)
    price_text = f"{average.quantize(Decimal('0.01')):,.2f}"
    is_sample_data = all(price.is_sample_data for price in prices)
    crop_label = (
        crop.local_name_sw if language == "sw" else
        crop.local_name_guz if language == "guz" else
        crop.name
    ) or crop.name
    sample_label = (
        {
            "en": " Sample prices.",
            "sw": " Bei za mfano.",
            "guz": " Sample prices.",
        }[language]
        if is_sample_data
        else ""
    )
    messages = {
        "en": f"{crop_label} in {ward.name}: KES {price_text}/kg ({latest_date:%d %b}).{sample_label}",
        "sw": f"{crop_label} {ward.name}: KES {price_text}/kg ({latest_date:%d %b}).{sample_label}",
        "guz": f"{crop_label}, {ward.name}: KES {price_text}/kg ({latest_date:%d %b}).{sample_label}",
    }
    message = messages[language][:160]
    return {
        "crop": crop.name,
        "crop_local_name": crop_label,
        "ward": ward.name,
        "currency": "KES",
        "unit": "kg",
        "average_price_per_kg": str(average.quantize(Decimal("0.01"))),
        "date": latest_date.isoformat(),
        "market_count": len(prices),
        "is_sample_data": is_sample_data,
        "sms_text": message,
        "ussd_text": message,
    }
