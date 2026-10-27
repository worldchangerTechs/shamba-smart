import json
import logging
import time
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Farmer, User, Ward
from alerts.models import Alert, AlertDelivery, Rule
from farms.models import Crop, Farm, Planting
from gateway.models import AuditLog, SmsBatch, SmsMessage, SmsSkippedRecipient

from .phone import normalize_kenyan_phone
from .providers import SmsProviderError, get_sms_provider

logger = logging.getLogger(__name__)


WARNING_TEMPLATES = {
    "heavy_rain_steep": {
        "title": "Heavy rain on steep slopes",
        "en": "Heavy rain is expected. Check drainage and protect soil on steep slopes.",
        "sw": "Mvua kubwa inatarajiwa. Kagua mifereji na ulinde udongo kwenye miteremko.",
        "guz": "Ekegusii text needs native-speaker review: heavy rain is expected; protect soil.",
    },
    "armyworm_nearby": {
        "title": "Fall armyworm reported nearby",
        "en": "Fall armyworm is confirmed nearby. Check maize leaves and report new damage.",
        "sw": "Fall armyworm imethibitishwa karibu. Kagua majani ya mahindi na uripoti uharibifu.",
        "guz": "Ekegusii text needs native-speaker review: check maize for fall armyworm.",
    },
    "tomato_blight": {
        "title": "Tomato blight conditions",
        "en": "Cool, wet weather may cause tomato blight. Check leaves and avoid wetting them.",
        "sw": "Baridi na unyevu vinaweza kusababisha blight ya nyanya. Kagua majani.",
        "guz": "Ekegusii text needs native-speaker review: inspect tomato leaves in cool wet weather.",
    },
    "dry_spell": {
        "title": "Dry spell",
        "en": "Dry weather is expected. Mulch crops and water early if water is available.",
        "sw": "Hali kavu inatarajiwa. Weka matandazo na mwagilia mapema ikiwa maji yapo.",
        "guz": "Ekegusii text needs native-speaker review: mulch crops during the dry spell.",
    },
    "price_spike": {
        "title": "Market price increase",
        "en": "Local crop prices have risen. Compare buyers and confirm prices before selling.",
        "sw": "Bei za mazao zimepanda. Linganisha wanunuzi na uthibitishe bei kabla ya kuuza.",
        "guz": "Ekegusii text needs native-speaker review: compare buyers before selling.",
    },
    "safe_reentry": {
        "title": "Safe re-entry after spraying",
        "en": "Do not enter the sprayed field until the product re-entry time has passed.",
        "sw": "Usiingie shambani baada ya kunyunyiza hadi muda wa kusubiri upite.",
        "guz": "Ekegusii text needs native-speaker review: wait before entering a sprayed field.",
    },
}

NON_URGENT_SEVERITIES = {Rule.Severity.LOW, Rule.Severity.MEDIUM}
URGENT_SEVERITIES = {Rule.Severity.HIGH, Rule.Severity.CRITICAL}


def _require_sender(user):
    if not user or not user.is_authenticated or not user.is_active or user.role not in {
        User.Role.ADMIN,
        User.Role.OFFICER,
    }:
        raise PermissionDenied("Only an admin or officer can send warning batches.")


def _parse_payload(payload):
    if not isinstance(payload, dict):
        raise ValidationError({"detail": "A warning configuration is required."})
    template_code = payload.get("template_code")
    template = WARNING_TEMPLATES.get(template_code)
    if template is None:
        raise ValidationError({"template_code": "Choose a supported warning template."})

    language = payload.get("language", "en")
    if language not in {"en", "sw", "guz"}:
        raise ValidationError({"language": "Choose English, Kiswahili or Ekegusii."})
    message = payload.get("message", template[language])
    if not isinstance(message, str) or not message.strip():
        raise ValidationError({"message": "Enter a warning message."})
    message = message.strip()
    if len(message) > 160:
        raise ValidationError({"message": "SMS messages must be 160 characters or fewer."})

    severity = payload.get("severity", Rule.Severity.MEDIUM)
    if severity not in dict(Rule.Severity.choices):
        raise ValidationError({"severity": "Choose a valid severity."})

    target = payload.get("target")
    if not isinstance(target, dict):
        raise ValidationError({"target": "Choose a recipient target."})
    target_type = target.get("type")
    target_value = target.get("value")
    if target_type not in {"ward", "crop", "slope", "demo"}:
        raise ValidationError({"target": "Choose a ward, crop, slope class or Demo Group."})
    if target_type != "demo" and target_value in (None, ""):
        raise ValidationError({"target": "Select a value for the chosen target."})

    return {
        "template_code": template_code,
        "template": template,
        "language": language,
        "message": message,
        "severity": severity,
        "target_type": target_type,
        "target_value": target_value,
    }


def _week_start(now):
    local_now = timezone.localtime(now)
    return local_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=local_now.weekday())


def _base_farmers(user, target_type, target_value):
    farmers = Farmer.objects.filter(user__is_active=True).select_related(
        "user", "ward", "main_crop"
    )
    if target_type == "ward":
        ward = Ward.objects.filter(pk=target_value).first()
        if ward is None:
            raise ValidationError({"target": "The selected ward does not exist."})
        farmers = farmers.filter(ward=ward)
        description = f"Ward: {ward.name}"
    elif target_type == "crop":
        crop = Crop.objects.filter(pk=target_value).first()
        if crop is None:
            raise ValidationError({"target": "The selected crop does not exist."})
        matching_farmers = Planting.objects.filter(crop=crop).values("farm__farmer_id")
        farmers = farmers.filter(
            Q(main_crop_id=crop.pk) | Q(pk__in=matching_farmers)
        ).distinct()
        description = f"Crop: {crop.name}"
    elif target_type == "slope":
        slope = str(target_value).upper()
        if slope not in Farm.SlopeClass.values:
            raise ValidationError({"target": "Choose flat, gentle or steep slope."})
        farmers = farmers.filter(farms__slope_class=slope).distinct()
        description = f"Slope: {slope.title()}"
    else:
        if user.role != User.Role.ADMIN:
            raise PermissionDenied("Only admins can target the Demo Group.")
        return farmers.none(), "Demo Group"

    if user.role == User.Role.OFFICER:
        assigned_wards = user.assigned_wards.values_list("pk", flat=True)
        if target_type == "ward" and not user.assigned_wards.filter(
            pk=target_value
        ).exists():
            raise PermissionDenied("Officers can send only to their assigned wards.")
        farmers = farmers.filter(ward_id__in=assigned_wards)
    return farmers, description


def _eligible_recipients(user, payload, now):
    farmers, description = _base_farmers(
        user, payload["target_type"], payload["target_value"]
    )
    eligible = []
    skipped = []

    if payload["target_type"] == "demo":
        for value in settings.DEMO_RECIPIENTS:
            try:
                phone = normalize_kenyan_phone(value)
            except ValueError:
                skipped.append({"phone": value, "reason": "invalid_phone"})
                continue
            eligible.append({"farmer": None, "phone": phone})
        return eligible, skipped, description

    week_start = _week_start(now)
    message_counts = dict(
        SmsMessage.objects.filter(
            farmer__in=farmers,
            batch__severity__in=NON_URGENT_SEVERITIES,
            batch__created_at__gte=week_start,
            status__in=[
                SmsMessage.Status.QUEUED,
                SmsMessage.Status.SENT,
                SmsMessage.Status.DELIVERED,
            ],
        )
        .values("farmer_id")
        .annotate(total=Count("pk"))
        .values_list("farmer_id", "total")
    )
    for farmer in farmers:
        reason = None
        if not farmer.user.consent_sms:
            reason = "no_sms_consent"
        else:
            try:
                phone = normalize_kenyan_phone(farmer.user.phone)
            except ValueError:
                phone = ""
                reason = "invalid_phone"
            if (
                reason is None
                and payload["severity"] in NON_URGENT_SEVERITIES
                and message_counts.get(farmer.pk, 0) >= 3
            ):
                reason = "weekly_cap"
        if reason:
            skipped.append(
                {"farmer": farmer, "phone": farmer.user.phone, "reason": reason}
            )
        else:
            eligible.append({"farmer": farmer, "phone": phone})
    return eligible, skipped, description


def preview_warning_batch(user, payload, now=None):
    _require_sender(user)
    parsed = _parse_payload(payload)
    now = now or timezone.now()
    eligible, skipped, description = _eligible_recipients(user, parsed, now)
    return {
        "recipient_count": len(eligible),
        "skipped_count": len(skipped),
        "skipped": [
            {"phone": item.get("phone", ""), "reason": item["reason"]}
            for item in skipped
        ],
        "message": parsed["message"],
        "template_code": parsed["template_code"],
        "target_description": description,
        "provider": settings.SMS_PROVIDER,
    }


def _update_delivery(message, status):
    if not message.alert_id:
        return
    delivery = AlertDelivery.objects.filter(
        alert_id=message.alert_id, channel=AlertDelivery.Channel.SMS
    ).first()
    if delivery is None:
        return
    if status == SmsMessage.Status.DELIVERED:
        delivery.sent_at = delivery.sent_at or timezone.now()
        delivery.delivered = True
    elif status == SmsMessage.Status.SENT:
        delivery.sent_at = delivery.sent_at or timezone.now()
    elif status == SmsMessage.Status.FAILED:
        delivery.delivered = False
    delivery.save(update_fields=("sent_at", "delivered"))


def _append_provider_batch_id(batch, provider_batch_id):
    if not provider_batch_id:
        return
    try:
        batch_ids = json.loads(batch.provider_batch_id) if batch.provider_batch_id else []
    except json.JSONDecodeError:
        batch_ids = [batch.provider_batch_id]
    if provider_batch_id not in batch_ids:
        batch_ids.append(provider_batch_id)
        batch.provider_batch_id = json.dumps(batch_ids)
        batch.save(update_fields=("provider_batch_id",))


def send_warning_batch(
    user,
    payload=None,
    now=None,
    recipients_override=None,
    enqueue=True,
    *,
    batch_id=None,
    message_ids=None,
):
    _require_sender(user)
    if batch_id is not None:
        batch = SmsBatch.objects.select_related("created_by").get(pk=batch_id)
        if batch.created_by_id != user.pk:
            raise PermissionDenied("Only the batch creator can process this send.")
        pending_query = batch.messages.filter(status=SmsMessage.Status.QUEUED)
        if message_ids is None:
            pending_query = batch.messages.filter(
                status__in=[SmsMessage.Status.QUEUED, SmsMessage.Status.FAILED]
            )
        else:
            pending_query = pending_query.filter(pk__in=message_ids)
        pending = list(pending_query.order_by("pk"))
        if not pending:
            return batch
        try:
            provider = get_sms_provider(batch.provider)
        except Exception as exc:
            error = str(exc).strip() or "SMS provider could not be initialized."
            for message in pending:
                message.status = SmsMessage.Status.FAILED
                message.error = error[:500]
                message.updated_at = timezone.now()
                message.save(update_fields=("status", "error", "updated_at"))
                _update_delivery(message, SmsMessage.Status.FAILED)
            logger.exception(
                "Could not initialize the SMS provider for batch %s.", batch.pk
            )
            raise SmsProviderError(error) from exc

        for offset in range(0, len(pending), 10):
            chunk = pending[offset : offset + 10]
            try:
                response = provider.send(
                    [message.phone for message in chunk], chunk[0].body
                )
                _append_provider_batch_id(batch, response.get("batch_id", ""))
                provider_message_ids = response.get("message_ids", [])
                if provider.name == "simulator":
                    time.sleep(1)
                for index, message in enumerate(chunk):
                    if index < len(provider_message_ids):
                        message.provider_message_id = str(provider_message_ids[index])
                    message.status = SmsMessage.Status.SENT
                    message.error = ""
                    message.updated_at = timezone.now()
                    message.save(
                        update_fields=(
                            "status",
                            "error",
                            "updated_at",
                            "provider_message_id",
                        )
                    )
                    _update_delivery(message, SmsMessage.Status.SENT)
                if provider.name == "simulator":
                    time.sleep(1)
                    for message in chunk:
                        message.status = SmsMessage.Status.DELIVERED
                        message.updated_at = timezone.now()
                        message.save(update_fields=("status", "updated_at"))
                        _update_delivery(message, SmsMessage.Status.DELIVERED)
            except Exception as exc:
                error = str(exc).strip() or "SMS provider could not send this message."
                for message in chunk:
                    message.status = SmsMessage.Status.FAILED
                    message.error = error[:500]
                    message.updated_at = timezone.now()
                    message.save(update_fields=("status", "error", "updated_at"))
                    _update_delivery(message, SmsMessage.Status.FAILED)
                logger.exception(
                    "SMS provider failed for batch %s, chunk starting at %s.",
                    batch.pk,
                    offset,
                )
                raise SmsProviderError(error) from exc
            if offset + 10 < len(pending):
                time.sleep(0.5)
        return batch

    parsed = _parse_payload(payload)
    now = now or timezone.now()
    if recipients_override is not None:
        if user.role != User.Role.ADMIN:
            raise PermissionDenied("Only admins can send a direct SMS test.")
        try:
            test_recipients = [
                {"farmer": None, "phone": normalize_kenyan_phone(value)}
                for value in recipients_override
            ]
        except ValueError as exc:
            raise ValidationError({"to": str(exc)}) from exc
        eligible = test_recipients
        skipped = []
        description = "SMS test"
    else:
        eligible, skipped, description = _eligible_recipients(user, parsed, now)

    with transaction.atomic():
        if any(item["farmer"] for item in eligible):
            farmer_ids = [item["farmer"].pk for item in eligible if item["farmer"]]
            list(Farmer.objects.select_for_update().filter(pk__in=farmer_ids))
            eligible, skipped, description = _eligible_recipients(
                user, parsed, now
            )

        batch = SmsBatch.objects.create(
            created_by=user,
            provider=settings.SMS_PROVIDER,
            template_code=parsed["template_code"],
            target_description=description,
            severity=parsed["severity"],
            total=len(eligible),
        )
        alerts = []
        for recipient in eligible:
            farmer = recipient["farmer"]
            if farmer:
                alerts.append(
                    Alert(
                        farmer=farmer,
                        farm=farmer.farms.order_by("pk").first(),
                        severity=parsed["severity"],
                        priority=100,
                        title=parsed["template"]["title"],
                        body_by_language={
                            "en": parsed["message"],
                            "sw": parsed["message"],
                            "guz": parsed["message"],
                        },
                        source_key=f"sms-batch:{uuid4().hex}",
                    )
                )
        created_alerts = Alert.objects.bulk_create(alerts)
        alerts_by_farmer = {alert.farmer_id: alert for alert in created_alerts}
        messages = [
            SmsMessage(
                batch=batch,
                farmer=recipient["farmer"],
                alert=alerts_by_farmer.get(recipient["farmer"].pk)
                if recipient["farmer"]
                else None,
                phone=recipient["phone"],
                body=parsed["message"],
            )
            for recipient in eligible
        ]
        SmsMessage.objects.bulk_create(messages)
        for alert in created_alerts:
            AlertDelivery.objects.create(
                alert=alert,
                channel=AlertDelivery.Channel.SMS,
                delivered=False,
            )
        SmsSkippedRecipient.objects.bulk_create(
            [
                SmsSkippedRecipient(
                    batch=batch,
                    farmer=item.get("farmer"),
                    phone=item.get("phone", ""),
                    reason=item["reason"],
                )
                for item in skipped
            ]
        )
        AuditLog.objects.create(
            user=user,
            batch=batch,
            template_code=parsed["template_code"],
            target_description=description,
            count=len(eligible),
            provider=settings.SMS_PROVIDER,
        )
        if enqueue and eligible:
            transaction.on_commit(
                lambda batch_id=batch.pk: _queue_sms_batch(batch_id)
            )
    return batch


def _queue_sms_batch(batch_id):
    from .tasks import process_sms_batch

    process_sms_batch.delay(batch_id)
