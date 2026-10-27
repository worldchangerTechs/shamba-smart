from datetime import timedelta
from math import atan2, cos, radians, sin, sqrt

from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from alerts.models import Alert, Rule
from farms.models import Farm
from pests.models import Outbreak, PestKnowledge, PestReport

OUTBREAK_RADIUS_KM = 5
OUTBREAK_THRESHOLD = 3
OUTBREAK_WINDOW_DAYS = 7
SYMPTOM_LABELS = {
    "leaf_holes": "holes in leaves",
    "frass": "sawdust-like waste near leaves",
    "aphid_clusters": "clusters of small insects",
    "sticky_leaves": "sticky leaves",
    "whitefly_cloud": "small white insects flying from leaves",
    "leafminer_tunnels": "tunnels inside leaves",
    "dark_leaf_spots": "dark spots on leaves",
    "white_leaf_growth": "white growth under leaves",
    "dark_fruit_lesions": "dark lesions on fruit",
    "berry_drop": "berries dropping early",
}


def haversine_km(lat1, lng1, lat2, lng2):
    radius = 6371
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lng / 2) ** 2
    )
    return radius * 2 * atan2(sqrt(value), sqrt(1 - value))


def _outbreak_level(count):
    if count >= 10:
        return Outbreak.Level.CRITICAL
    if count >= 6:
        return Outbreak.Level.HIGH
    if count >= OUTBREAK_THRESHOLD:
        return Outbreak.Level.MEDIUM
    return Outbreak.Level.LOW


def _nearby_growers(report):
    if report.lat is None or report.lng is None or report.crop_id is None:
        return []
    latitude_delta = OUTBREAK_RADIUS_KM / 110.574
    longitude_scale = max(abs(cos(radians(report.lat))), 0.01)
    longitude_delta = OUTBREAK_RADIUS_KM / (111.320 * longitude_scale)
    farms = (
        Farm.objects.filter(
            plantings__crop_id=report.crop_id,
            lat__gte=report.lat - latitude_delta,
            lat__lte=report.lat + latitude_delta,
            lng__gte=report.lng - longitude_delta,
            lng__lte=report.lng + longitude_delta,
        )
        .select_related("farmer__user", "farmer__ward")
        .distinct()
    )
    by_farmer = {}
    for farm in farms:
        distance = haversine_km(report.lat, report.lng, farm.lat, farm.lng)
        if distance <= OUTBREAK_RADIUS_KM:
            current = by_farmer.get(farm.farmer_id)
            if current is None or distance < current[0]:
                by_farmer[farm.farmer_id] = (distance, farm)
    return [value[1] for value in by_farmer.values()]


def update_outbreak_for_report(report, now=None):
    if report.status != PestReport.Status.CONFIRMED or not report.pest_name:
        return None
    now = now or timezone.now()
    rule = Rule.objects.filter(code="OUTBREAK_NEARBY", active=True).first()
    conditions = rule.condition_json if rule else {}
    threshold = int(conditions.get("confirmed_reports", conditions.get("count", OUTBREAK_THRESHOLD)))
    window_days = int(conditions.get("days", OUTBREAK_WINDOW_DAYS))
    since = now - timedelta(days=window_days)
    recent = PestReport.objects.filter(
        ward_id=report.ward_id,
        pest_name=report.pest_name,
        status=PestReport.Status.CONFIRMED,
        created_at__gte=since,
    )
    count = recent.count()
    started_at = recent.aggregate(first=Min("created_at"))["first"] or now
    with transaction.atomic():
        outbreak, _ = Outbreak.objects.update_or_create(
            ward_id=report.ward_id,
            pest_name=report.pest_name,
            defaults={
                "crop_id": report.crop_id,
                "started_at": started_at,
                "confirmed_count": count,
                "level": _outbreak_level(count),
            },
        )
        if count < threshold or report.crop_id is None:
            return outbreak

        if rule is None:
            return outbreak
        pest_label = report.get_pest_name_display()
        crop_name = report.crop.name
        source_key = (
            f"pest-outbreak:{outbreak.pk}:{report.crop_id}:"
            f"{started_at.date().isoformat()}"
        )
        for farm in _nearby_growers(report):
            farmer = farm.farmer
            Alert.objects.get_or_create(
                farmer=farmer,
                rule=rule,
                source_key=source_key,
                defaults={
                    "farm": farm,
                    "severity": Rule.Severity.HIGH,
                    "priority": 100,
                    "title": f"{pest_label} reported nearby",
                    "body_by_language": {
                        "en": (
                            f"{count} confirmed {pest_label} reports were recorded "
                            f"in {report.ward.name} in {window_days} days. Check your {crop_name} "
                            "and contact an officer if you see symptoms."
                        ),
                        "sw": (
                            f"Kesi {count} zilizothibitishwa za {pest_label} zimeripotiwa "
                            f"{report.ward.name} ndani ya siku {window_days}. Kagua {crop_name} "
                            "na uwasiliane na afisa ukiona dalili."
                        ),
                        "guz": (
                            f"[Guz translation placeholder] {count} confirmed "
                            f"{pest_label} reports nearby. Check your {crop_name}."
                        ),
                    },
                    "status": Alert.Status.OPEN,
                },
            )
    return outbreak


def identify_likely_pests(symptom_icons, language="en"):
    selected = set(symptom_icons)
    matches = []
    for knowledge in PestKnowledge.objects.all():
        observed = selected.intersection(knowledge.symptom_icons)
        if not observed:
            continue
        fraction = len(observed) / len(selected)
        confidence = (
            "More likely" if fraction >= 2 / 3 else "Possible"
        )
        symptoms = knowledge.symptoms_by_language.get(language) or knowledge.symptoms_by_language.get("en", [])
        matches.append(
            {
                "pest_name": knowledge.pest_name,
                "pest_label": knowledge.get_pest_name_display(),
                "confidence": confidence,
                "matching_symptom_icons": sorted(observed),
                "matching_symptoms": [
                    SYMPTOM_LABELS.get(icon, icon) for icon in sorted(observed)
                ],
                "knowledge_base_entry": {
                    "symptoms": symptoms,
                    "photo": knowledge.photo.url if knowledge.photo else None,
                },
                "guide_not_diagnosis": True,
            }
        )
    matches.sort(
        key=lambda item: (
            0 if item["confidence"] == "More likely" else 1,
            -len(item["matching_symptom_icons"]),
            item["pest_name"],
        )
    )
    return {
        "notice": (
            "This symptom guide suggests possibilities only. It is not a diagnosis. "
            "Ask an agricultural officer to verify the pest."
        ),
        "results": matches[:3],
    }
