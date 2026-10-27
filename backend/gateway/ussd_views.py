"""
USSD session state machine for the Shamba gateway.

Africa's Talking POSTs to POST /api/ussd/ with:
  sessionId, phoneNumber, networkCode, serviceCode, text

``text`` is the full dial string accumulated so far, e.g. "1*2" means the
user chose menu item 1 then sub-menu item 2.

Session state is stored in Django's cache backend (keyed by sessionId).

Main menu
─────────
1 Weather & planting
2 My soil
3 Pest alert
4 Prices
5 Safe spraying
6 Erosion help
7 Learn
8 Waste
9 Language

Unregistered flow (triggered when phone is not found in DB):
  Step REG_WARD  → ask for ward name
  Step REG_CROP  → ask for primary crop
  Step REG_SLOPE → ask for slope class (1 Flat / 2 Gentle / 3 Steep)
  → create User + Farmer, then show main menu
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import Farmer, User, Ward
from farms.models import Crop, Farm
from market.models import MarketPrice
from pests.models import PestReport
from weather.models import WeatherSnapshot

from .at_client import ussd_continue, ussd_end

logger = logging.getLogger(__name__)

SESSION_TTL = 300  # seconds – AT sessions expire after 2 min idle; 5 min is safe
_SLOPE_MAP = {"1": "FLAT", "2": "GENTLE", "3": "STEEP"}

MAIN_MENU = (
    "CON ShambaHub\n"
    "1 Weather & planting\n"
    "2 My soil\n"
    "3 Pest alert\n"
    "4 Prices\n"
    "5 Safe spraying\n"
    "6 Erosion help\n"
    "7 Learn\n"
    "8 Waste\n"
    "9 Language"
)


# ── session helpers ────────────────────────────────────────────────────────────

def _cache_key(session_id: str) -> str:
    return f"ussd:session:{session_id}"


def _get_session(session_id: str) -> dict:
    return cache.get(_cache_key(session_id)) or {}


def _set_session(session_id: str, data: dict) -> None:
    cache.set(_cache_key(session_id), data, timeout=SESSION_TTL)


def _clear_session(session_id: str) -> None:
    cache.delete(_cache_key(session_id))


# ── farmer lookup ──────────────────────────────────────────────────────────────

def _find_farmer(phone: str) -> Farmer | None:
    try:
        user = User.objects.get(phone=phone)
        return getattr(user, "farmer_profile", None)
    except User.DoesNotExist:
        return None


def _normalise_phone(raw: str) -> str:
    """Strip leading zeros and ensure +254 prefix."""
    raw = raw.strip()
    if raw.startswith("0"):
        raw = "+254" + raw[1:]
    if not raw.startswith("+"):
        raw = "+" + raw
    return raw


# ── registration flow ──────────────────────────────────────────────────────────

def _handle_registration(session: dict, text_step: str, phone: str) -> str:
    """
    Multi-step registration.  ``session['reg_step']`` tracks progress.

    Returns a USSD string (CON … or END …).
    """
    step = session.get("reg_step", "ward")

    if step == "ward":
        session["reg_ward_raw"] = text_step
        session["reg_step"] = "crop"
        return ussd_continue("Enter your ward name\n(e.g. Nyamira, Masaba):")

    if step == "crop":
        session["reg_crop_raw"] = text_step
        session["reg_step"] = "slope"
        return ussd_continue(
            "Your slope:\n1 Flat\n2 Gentle\n3 Steep"
        )

    if step == "slope":
        slope = _SLOPE_MAP.get(text_step)
        if not slope:
            return ussd_continue(
                "Invalid. Your slope:\n1 Flat\n2 Gentle\n3 Steep"
            )
        # commit registration
        ward_name = session.get("reg_ward_raw", "Unknown")
        crop_name = session.get("reg_crop_raw", "Maize")
        try:
            ward, _ = Ward.objects.get_or_create(
                name__iexact=ward_name,
                defaults={
                    "name": ward_name.title(),
                    "sub_county": "Unknown",
                    "lat": -0.68,
                    "lng": 34.77,
                },
            )
        except Ward.MultipleObjectsReturned:
            ward = Ward.objects.filter(name__iexact=ward_name).first()

        with transaction.atomic():
            user, _ = User.objects.get_or_create(
                phone=phone,
                defaults={
                    "role": User.Role.FARMER,
                    "consent_sms": True,
                    "language": User.Language.SW,
                },
            )
            user.set_unusable_password()
            user.save()
            farmer, _ = Farmer.objects.get_or_create(
                user=user,
                defaults={
                    "ward": ward,
                    "literacy_level": Farmer.LiteracyLevel.MEDIUM,
                    "has_smartphone": False,
                },
            )
            crop, _ = Crop.objects.get_or_create(
                name__iexact=crop_name,
                defaults={
                    "name": crop_name.title(),
                    "water_needs": "medium",
                    "ideal_ph_min": 5.5,
                    "ideal_ph_max": 7.0,
                },
            )
            Farm.objects.get_or_create(
                farmer=farmer,
                name="Main Farm",
                defaults={
                    "lat": ward.lat,
                    "lng": ward.lng,
                    "size_acres": 1,
                    "slope_class": slope,
                    "soil_type": "Loam",
                },
            )

        session["reg_step"] = "done"
        session["registered"] = True
        return ussd_continue(
            f"Welcome, {ward_name} farmer!\n"
            + MAIN_MENU.replace("CON ", "")
        )

    return ussd_end("Registration error. Please try again.")


# ── menu handlers ─────────────────────────────────────────────────────────────

def _weather(farmer: Farmer | None) -> str:
    if farmer:
        snap = (
            WeatherSnapshot.objects.filter(ward=farmer.ward)
            .order_by("-date")
            .first()
        )
        if snap:
            rain = snap.rain_mm or 0
            temp = snap.temp_max or "--"
            rec = "Good day to plant." if rain < 5 else "Hold planting."
            return ussd_end(f"Rain:{rain:.0f}mm Tmp:{temp}C\n{rec}")
    return ussd_end("No weather data.\nCheck back later.")


def _soil(farmer: Farmer | None) -> str:
    if farmer:
        farm = farmer.farms.order_by("id").first()
        if farm:
            ph = farm.soil_ph or "N/A"
            slope = farm.slope_class
            return ussd_end(f"Soil: {farm.soil_type}\npH:{ph} Slope:{slope}")
    return ussd_end("No farm data.\nRegister a farm first.")


def _pest(farmer: Farmer | None) -> str:
    if farmer:
        report = (
            PestReport.objects.filter(farm__farmer=farmer)
            .order_by("-created_at")
            .first()
        )
        if report:
            return ussd_end(
                f"Last pest: {report.pest_name}\n"
                f"{report.created_at.strftime('%d/%m/%y')}\n"
                "SMS PEST for tips."
            )
    return ussd_end("No pest reports.\nSMS PEST for tips.")


def _prices(farmer: Farmer | None) -> str:
    if farmer:
        prices = MarketPrice.objects.filter(ward=farmer.ward).order_by("-date")[:2]
        if prices:
            lines = "\n".join(
                f"{p.crop.name[:6]}: KES{p.price_per_kg:.0f}" for p in prices
            )
            return ussd_end(f"Prices ({farmer.ward.name}):\n{lines}")
    prices = MarketPrice.objects.order_by("-date")[:2]
    if prices:
        lines = "\n".join(f"{p.crop.name[:6]}: KES{p.price_per_kg:.0f}" for p in prices)
        return ussd_end(f"Market prices:\n{lines}")
    return ussd_end("No price data now.\nSMS PRICE <crop>.")


def _spraying(farmer: Farmer | None) -> str:
    if farmer:
        snap = (
            WeatherSnapshot.objects.filter(ward=farmer.ward)
            .order_by("-date")
            .first()
        )
        if snap:
            # Use humidity as a proxy when wind is unavailable
            humid = snap.humidity or 0
            if humid > 80:
                return ussd_end("AVOID spraying.\nHigh humidity (>80%).\nRisk of drift.")
            return ussd_end("Safe to spray.\nHumidity OK.\nWear PPE.")
    return ussd_end("Spray early morning.\nWind <4m/s. Wear PPE.")


def _erosion(farmer: Farmer | None) -> str:
    if farmer:
        farm = farmer.farms.order_by("id").first()
        if farm and farm.slope_class == "STEEP":
            return ussd_end(
                "STEEP slope risk!\n"
                "Dig terraces. Plant\n"
                "grass strips now."
            )
        elif farm:
            return ussd_end(
                "Slope OK. Mulch rows.\nAvoid bare soil.")
    return ussd_end("Mulch & cover crop.\nAvoid bare soil.")


def _learn(farmer: Farmer | None) -> str:
    return ussd_end("ShambaHub Academy\nOpen app to learn.\nEarn badges!")


def _waste(farmer: Farmer | None) -> str:
    return ussd_end("Organic: compost it.\nChemical: take to\nnearest depot.")


def _language(session: dict) -> str:
    session["choosing_lang"] = True
    return ussd_continue("Choose language:\n1 English\n2 Kiswahili\n3 Ekegusii")


def _set_language(farmer: Farmer | None, choice: str) -> str:
    lang_map = {"1": "en", "2": "sw", "3": "guz"}
    lang = lang_map.get(choice)
    if not lang:
        return ussd_end("Invalid choice.")
    if farmer:
        farmer.user.language = lang
        farmer.user.save(update_fields=["language"])
    return ussd_end(f"Language set to {['English','Kiswahili','Ekegusii'][int(choice)-1]}.")


MENU_DISPATCH = {
    "1": _weather,
    "2": _soil,
    "3": _pest,
    "4": _prices,
    "5": _spraying,
    "6": _erosion,
    "7": _learn,
    "8": _waste,
}


# ── main view ─────────────────────────────────────────────────────────────────

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def ussd_callback(request: Request) -> Response:
    """
    Africa's Talking USSD callback endpoint.

    AT sends form-encoded data; DRF parses it via request.data.
    """
    session_id = request.data.get("sessionId", "")
    phone = _normalise_phone(request.data.get("phoneNumber", ""))
    text: str = request.data.get("text", "")  # full accumulated string

    session = _get_session(session_id)
    farmer = _find_farmer(phone)

    # Split the accumulated text into steps
    parts = [p for p in text.split("*") if p != ""] if text else []
    # The current user input is the last part (or empty if first dial)
    current = parts[-1] if parts else ""

    # ── Unregistered path ─────────────────────────────────────────────────────
    if farmer is None and not session.get("registered"):
        if not parts:
            # First contact – start registration flow
            session["reg_step"] = "ward"
            _set_session(session_id, session)
            return Response(
                ussd_continue(
                    "Welcome to ShambaHub!\n"
                    "Not registered yet.\n"
                    "Enter your ward name:"
                ),
                content_type="text/plain",
            )
        response = _handle_registration(session, current, phone)
        _set_session(session_id, session)
        if response.startswith("END"):
            _clear_session(session_id)
        return Response(response, content_type="text/plain")

    # Re-fetch farmer in case registration just completed
    if farmer is None:
        farmer = _find_farmer(phone)

    # ── Registered: root menu ─────────────────────────────────────────────────
    if not parts:
        _set_session(session_id, session)
        return Response(MAIN_MENU, content_type="text/plain")

    root = parts[0]

    # Language sub-menu
    if root == "9":
        if len(parts) == 1:
            result = _language(session)
            _set_session(session_id, session)
            return Response(result, content_type="text/plain")
        result = _set_language(farmer, parts[1] if len(parts) > 1 else "")
        _clear_session(session_id)
        return Response(result, content_type="text/plain")

    # All other menu items are single-step
    handler = MENU_DISPATCH.get(root)
    if handler:
        result = handler(farmer)
        _clear_session(session_id)
        return Response(result, content_type="text/plain")

    _clear_session(session_id)
    return Response(ussd_end("Invalid option."), content_type="text/plain")
