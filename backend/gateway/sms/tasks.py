import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from gateway.models import SmsBatch, SmsMessage

from .providers import SmsProviderError
from .service import send_warning_batch

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_sms_batch(self, batch_id, message_ids=None):
    batch = SmsBatch.objects.select_related("created_by").get(pk=batch_id)
    sender = batch.created_by
    pending = batch.messages.filter(
        status__in=[SmsMessage.Status.QUEUED, SmsMessage.Status.FAILED]
    )
    if message_ids is not None:
        pending = pending.filter(pk__in=message_ids)
    if (
        not sender.is_active
        or sender.role not in {"ADMIN", "OFFICER"}
    ):
        error = "No active admin or officer is authorized to send this batch."
        pending.update(
            status=SmsMessage.Status.FAILED,
            error=error,
            updated_at=timezone.now(),
        )
        logger.error("SMS batch %s has no authorized sender.", batch_id)
        return {"batch_id": batch.pk, "failed": pending.count(), "error": error}

    try:
        send_warning_batch(
            sender,
            batch_id=batch.pk,
            message_ids=message_ids,
        )
    except SmsProviderError as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                args=(batch.pk, message_ids),
                countdown=2 ** (self.request.retries + 1),
            )
        return {
            "batch_id": batch.pk,
            "failed": batch.messages.filter(
                status=SmsMessage.Status.FAILED
            ).count(),
            "error": str(exc),
        }
    return {
        "batch_id": batch.pk,
        "processed": batch.messages.filter(
            status__in=[SmsMessage.Status.SENT, SmsMessage.Status.DELIVERED]
        ).count(),
    }


@shared_task
def retry_failed_sms(batch_id, requested_by_id):
    User = get_user_model()
    batch = SmsBatch.objects.select_related("created_by").get(pk=batch_id)
    requested_by = User.objects.get(pk=requested_by_id)
    if (
        not requested_by.is_active
        or requested_by.role not in {"ADMIN", "OFFICER"}
    ):
        logger.warning("Rejected unauthorized retry for SMS batch %s.", batch_id)
        return {"batch_id": batch.pk, "retried": 0, "reason": "unauthorized_sender"}

    with transaction.atomic():
        failed = batch.messages.select_for_update().filter(
            status=SmsMessage.Status.FAILED
        )
        failed_ids = list(failed.values_list("pk", flat=True))
        if requested_by.role == "OFFICER":
            assigned_ward_ids = list(
                requested_by.assigned_wards.values_list("pk", flat=True)
            )
            if not assigned_ward_ids or failed.filter(
                farmer__isnull=True
            ).exists() or failed.exclude(
                farmer__ward_id__in=assigned_ward_ids
            ).exists():
                return {
                    "batch_id": batch.pk,
                    "retried": 0,
                    "reason": "outside_assigned_wards",
                }
        retried = failed.update(
            status=SmsMessage.Status.QUEUED,
            error="",
            updated_at=timezone.now(),
        )
        if retried:
            transaction.on_commit(
                lambda: process_sms_batch.delay(batch.pk, failed_ids)
            )
    return {"batch_id": batch.pk, "retried": retried}
