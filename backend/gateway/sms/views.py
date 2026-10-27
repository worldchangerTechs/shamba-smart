import json
import logging

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from accounts.models import User
from gateway.models import AuditLog, SmsBatch, SmsMessage
from alerts.models import AlertDelivery
from .providers import VendelProvider, get_sms_provider
from .service import preview_warning_batch, send_warning_batch

logger = logging.getLogger(__name__)


class AdminOrOfficerPermission(BasePermission):
    message = "Only an admin or officer can use warning management."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.ADMIN, User.Role.OFFICER}
        )


class SmsSendRateThrottle(UserRateThrottle):
    scope = "sms_send"


def _officer_can_access_batch(user, batch):
    if user.role == User.Role.ADMIN or user.is_superuser:
        return True
    assigned_ward_ids = list(user.assigned_wards.values_list("pk", flat=True))
    if not assigned_ward_ids:
        return False
    return not batch.messages.filter(farmer__isnull=False).exclude(
        farmer__ward_id__in=assigned_ward_ids
    ).exists() and not batch.messages.filter(farmer__isnull=True).exists()


def _batch_payload(batch):
    messages = list(
        batch.messages.select_related("farmer__user", "farmer__ward").order_by("pk")
    )
    counts = {
        row["status"].lower(): row["total"]
        for row in batch.messages.values("status").annotate(total=Count("pk"))
    }
    return {
        "id": batch.pk,
        "provider": batch.provider,
        "provider_batch_id": batch.provider_batch_id,
        "template_code": batch.template_code,
        "target_description": batch.target_description,
        "total": batch.total,
        "created_at": batch.created_at,
        "counts": {
            key: counts.get(key, 0)
            for key in ("queued", "sent", "delivered", "failed")
        },
        "messages": [
            {
                "id": message.pk,
                "farmer": message.farmer_id,
                "name": (
                    f"{message.farmer.user.first_name} {message.farmer.user.last_name}".strip()
                    if message.farmer_id
                    else "Demo recipient"
                ),
                "phone": message.phone,
                "body": message.body,
                "status": message.status,
                "error": message.error,
                "updated_at": message.updated_at,
            }
            for message in messages
        ],
        "skipped": [
            {
                "farmer": item.farmer_id,
                "phone": item.phone,
                "reason": item.reason,
            }
            for item in batch.skipped_recipients.all()
        ],
    }


def _refresh_vendel_status(batch):
    if batch.provider != SmsBatch.Provider.VENDEL or not batch.provider_batch_id:
        return None
    try:
        provider_batch_ids = json.loads(batch.provider_batch_id)
    except json.JSONDecodeError:
        provider_batch_ids = [batch.provider_batch_id]
    if not isinstance(provider_batch_ids, list):
        provider_batch_ids = [str(provider_batch_ids)]
    try:
        provider = VendelProvider()
        for provider_batch_id in provider_batch_ids:
            result = provider.status(str(provider_batch_id))
            for record in result.get("messages", []):
                message_id = str(record.get("id") or "")
                recipient = str(record.get("recipient") or "")
                query = batch.messages.all()
                if message_id:
                    query = query.filter(provider_message_id=message_id)
                elif recipient:
                    query = query.filter(phone=recipient)
                else:
                    continue
                next_status = _status_for_webhook(record.get("status"))
                if next_status is None:
                    continue
                for message in query:
                    if message.status == SmsMessage.Status.DELIVERED:
                        continue
                    message.status = next_status
                    message.error = str(record.get("error_message") or "")[:500]
                    message.save(update_fields=("status", "error", "updated_at"))
                    if message.alert_id:
                        AlertDelivery.objects.filter(
                            alert_id=message.alert_id,
                            channel=AlertDelivery.Channel.SMS,
                        ).update(
                            delivered=next_status == SmsMessage.Status.DELIVERED,
                            sent_at=timezone.now()
                            if next_status in {
                                SmsMessage.Status.SENT,
                                SmsMessage.Status.DELIVERED,
                            }
                            else None,
                        )
    except Exception as exc:
        logger.exception("Could not refresh Vendel status for batch %s.", batch.pk)
        return str(exc).strip() or "Vendel status is temporarily unavailable."
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
def warning_provider(request):
    provider_name = settings.SMS_PROVIDER
    if provider_name == "simulator":
        return Response(
            {"provider": provider_name, "base_url": None, "quota": {"remaining": None}}
        )
    try:
        provider = get_sms_provider()
        quota = provider.get_quota()
    except Exception as exc:
        logger.exception("Could not read the Vendel quota.")
        return Response(
            {
                "provider": provider_name,
                "base_url": settings.VENDEL_BASE_URL,
                "error": str(exc) or "Vendel is currently unreachable.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(
        {
            "provider": provider_name,
            "base_url": settings.VENDEL_BASE_URL,
            "quota": quota,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
def warning_preview(request):
    result = preview_warning_batch(request.user, request.data)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
@throttle_classes([SmsSendRateThrottle])
def warning_send(request):
    batch = send_warning_batch(request.user, request.data)
    return Response(_batch_payload(batch), status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
def warning_batch(request, batch_id):
    batch = SmsBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        raise NotFound("Warning batch not found.")
    if not _officer_can_access_batch(request.user, batch):
        raise PermissionDenied("You can access only batches for your assigned wards.")
    provider_error = _refresh_vendel_status(batch)
    batch.refresh_from_db()
    result = _batch_payload(batch)
    if provider_error:
        result["provider_error"] = provider_error
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
@throttle_classes([SmsSendRateThrottle])
def warning_retry(request, batch_id):
    batch = SmsBatch.objects.filter(pk=batch_id).first()
    if batch is None:
        raise NotFound("Warning batch not found.")
    if not _officer_can_access_batch(request.user, batch):
        raise PermissionDenied("You can retry only batches for your assigned wards.")
    failed_count = batch.messages.filter(status=SmsMessage.Status.FAILED).count()
    if failed_count:
        from .tasks import retry_failed_sms

        retry_failed_sms.delay(batch.pk, request.user.pk)
    return Response({"batch_id": batch.pk, "retry_queued": failed_count})


@api_view(["GET"])
@permission_classes([IsAuthenticated, AdminOrOfficerPermission])
def warning_audit_log(request):
    logs = AuditLog.objects.select_related("user", "batch")
    if request.user.role == User.Role.OFFICER and not request.user.is_superuser:
        assigned_ward_ids = request.user.assigned_wards.values_list("pk", flat=True)
        logs = logs.filter(
            batch__messages__farmer__ward_id__in=assigned_ward_ids
        ).distinct()
    return Response(
        [
            {
                "id": item.pk,
                "user": item.user.phone,
                "template_code": item.template_code,
                "target_description": item.target_description,
                "count": item.count,
                "provider": item.provider,
                "created_at": item.created_at,
                "batch_id": item.batch_id,
            }
            for item in logs[:200]
        ]
    )


def _valid_webhook_signature(raw_body, signature, secret):
    if not secret or not signature:
        return False
    try:
        from vendel_sdk import verify_webhook_signature
    except ImportError:
        logger.exception("Vendel webhook verification is unavailable.")
        return False
    return bool(verify_webhook_signature(raw_body, signature, secret))


def _webhook_records(payload):
    records = payload.get("messages", payload.get("recipients", []))
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        records = []
    if not records and any(key in payload for key in ("phone", "to", "recipient")):
        records = [payload]
    return records


def _status_for_webhook(value):
    normalized = str(value or "").strip().upper()
    if normalized in {"DELIVERED", "SUCCESS"}:
        return SmsMessage.Status.DELIVERED
    if normalized in {"SENT", "QUEUED", "ACCEPTED"}:
        return SmsMessage.Status.SENT
    if normalized in {"FAILED", "REJECTED", "UNDELIVERABLE"}:
        return SmsMessage.Status.FAILED
    return None


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def vendel_webhook(request):
    signature = request.headers.get("X-Webhook-Signature", "")
    raw_body = request._request.body
    if not _valid_webhook_signature(
        raw_body, signature, settings.VENDEL_WEBHOOK_SECRET
    ):
        return Response({"detail": "Invalid webhook signature."}, status=403)
    try:
        payload = json.loads(raw_body)
    except (TypeError, ValueError):
        return Response({"detail": "Webhook body must be valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return Response({"detail": "Webhook body must be a JSON object."}, status=400)

    batch_id = str(payload.get("batch_id") or "")
    updated = 0
    for record in _webhook_records(payload):
        if not isinstance(record, dict):
            continue
        next_status = _status_for_webhook(record.get("status"))
        if next_status is None:
            continue
        query = SmsMessage.objects.filter(batch__provider="vendel")
        message_id = str(record.get("message_id") or record.get("id") or "")
        phone = str(
            record.get("phone") or record.get("to") or record.get("recipient") or ""
        )
        if message_id:
            query = query.filter(provider_message_id=message_id)
        elif phone:
            query = query.filter(phone=phone)
        else:
            continue
        if batch_id:
            query = query.filter(batch__provider_batch_id__contains=batch_id)
        for message in query.select_related("batch").iterator():
            if message.status == SmsMessage.Status.DELIVERED:
                continue
            if message.status == next_status:
                continue
            if (
                message.status == SmsMessage.Status.FAILED
                and next_status == SmsMessage.Status.SENT
            ):
                continue
            message.status = next_status
            if next_status == SmsMessage.Status.FAILED:
                message.error = str(
                    record.get("error_message")
                    or record.get("error")
                    or "Vendel reported delivery failure."
                )[:500]
            else:
                message.error = ""
            message.save(update_fields=("status", "error", "updated_at"))
            updated += 1
            if message.alert_id:
                AlertDelivery.objects.filter(
                    alert_id=message.alert_id,
                    channel=AlertDelivery.Channel.SMS,
                ).update(
                    delivered=next_status == SmsMessage.Status.DELIVERED,
                    sent_at=timezone.now()
                    if next_status in {
                        SmsMessage.Status.SENT,
                        SmsMessage.Status.DELIVERED,
                    }
                    else None,
                )
    return Response({"updated": updated})
