import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from accounts.models import Ward
from weather.services.open_meteo import store_ward_weather

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def refresh_weather_snapshots(self):
    wards = list(Ward.objects.order_by("pk"))
    if not wards:
        logger.info("Weather refresh skipped because no wards are configured.")
        return {"wards": 0, "snapshots": 0}

    snapshot_count = 0
    today = timezone.localdate()
    for ward in wards:
        with transaction.atomic():
            snapshots = store_ward_weather(ward, today=today)
        snapshot_count += len(snapshots)

    logger.info(
        "Stored %s Open-Meteo snapshots across %s wards.",
        snapshot_count,
        len(wards),
    )
    return {"wards": len(wards), "snapshots": snapshot_count}
