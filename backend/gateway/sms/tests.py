import hashlib
import hmac
import json
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from alerts.models import AlertDelivery, Rule
from gateway.models import AuditLog, SmsBatch, SmsMessage
from gateway.sms import service as sms_service
from gateway.sms.phone import normalize_kenyan_phone
from gateway.sms.providers import VendelProvider
from gateway.sms.service import send_warning_batch
from gateway.sms.tasks import process_sms_batch, retry_failed_sms
from vendel_sdk import BatchStatus, Quota, SendSMSResponse


pytestmark = pytest.mark.django_db


def create_scope():
    ward = Ward.objects.create(
        name="Kisii Central", sub_county="Kisii Central", lat=-0.68, lng=34.76
    )
    officer = User.objects.create_user(
        phone="+254710000001", role=User.Role.OFFICER
    )
    officer.assigned_wards.add(ward)
    farmer_user = User.objects.create_user(
        phone="+254712000001",
        role=User.Role.FARMER,
        consent_sms=True,
    )
    farmer = Farmer.objects.create(
        user=farmer_user,
        ward=ward,
        literacy_level=Farmer.LiteracyLevel.MEDIUM,
    )
    return ward, officer, farmer


def warning_payload(ward_id, **overrides):
    payload = {
        "template_code": "heavy_rain_steep",
        "language": "en",
        "severity": "MEDIUM",
        "target": {"type": "ward", "value": ward_id},
        "message": "Heavy rain is expected. Check drainage and protect soil.",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0712 345 678", "+254712345678"),
        ("712345678", "+254712345678"),
        ("254712345678", "+254712345678"),
        ("+254712345678", "+254712345678"),
        ("0112345678", "+254112345678"),
    ],
)
def test_normalize_kenyan_phone_accepts_supported_formats(raw, expected):
    assert normalize_kenyan_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "+25471234", "0201234567", "123", "abc"])
def test_normalize_kenyan_phone_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        normalize_kenyan_phone(raw)


@pytest.mark.django_db(transaction=True)
def test_preview_skips_missing_consent_and_send_records_batch(monkeypatch):
    ward, officer, farmer = create_scope()
    no_consent_user = User.objects.create_user(
        phone="+254712000002", role=User.Role.FARMER, consent_sms=False
    )
    Farmer.objects.create(
        user=no_consent_user,
        ward=ward,
        literacy_level=Farmer.LiteracyLevel.MEDIUM,
    )
    queued = []
    monkeypatch.setattr(
        "gateway.sms.tasks.process_sms_batch.delay",
        lambda batch_id: queued.append(batch_id),
    )
    client = APIClient()
    client.force_authenticate(officer)

    preview = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(ward.pk),
        format="json",
    )
    assert preview.status_code == 200
    assert preview.data["recipient_count"] == 1
    assert preview.data["skipped_count"] == 1
    assert preview.data["skipped"][0]["reason"] == "no_sms_consent"
    assert len(preview.data["message"]) <= 160

    sent = client.post(
        "/api/admin/warnings/send/",
        warning_payload(ward.pk),
        format="json",
    )
    assert sent.status_code == 202
    batch = SmsBatch.objects.get(pk=sent.data["id"])
    assert batch.total == 1
    assert batch.created_by == officer
    assert batch.messages.get().farmer == farmer
    assert batch.skipped_recipients.get().reason == "no_sms_consent"
    assert AuditLog.objects.get(batch=batch).count == 1
    assert queued == [batch.pk]
    assert farmer.alerts.count() == 1
    assert AlertDelivery.objects.filter(alert__farmer=farmer).count() == 1


def test_over_length_sms_is_rejected_without_creating_a_batch():
    ward, officer, _farmer = create_scope()
    client = APIClient()
    client.force_authenticate(officer)
    response = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(ward.pk, message="x" * 161),
        format="json",
    )
    assert response.status_code == 400
    assert not SmsBatch.objects.exists()


def test_weekly_cap_skips_fourth_nonurgent_message_and_urgent_bypasses(monkeypatch):
    ward, officer, farmer = create_scope()
    for index in range(3):
        batch = SmsBatch.objects.create(
            created_by=officer,
            provider="simulator",
            template_code=f"old-{index}",
            target_description=f"Ward: {ward.name}",
            severity=Rule.Severity.MEDIUM,
            total=1,
        )
        SmsMessage.objects.create(
            batch=batch,
            farmer=farmer,
            phone=farmer.user.phone,
            body="Earlier warning.",
            status=SmsMessage.Status.DELIVERED,
        )
    client = APIClient()
    client.force_authenticate(officer)
    capped = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(ward.pk),
        format="json",
    )
    assert capped.status_code == 200
    assert capped.data["recipient_count"] == 0
    assert capped.data["skipped"][0]["reason"] == "weekly_cap"

    urgent = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(ward.pk, severity="HIGH"),
        format="json",
    )
    assert urgent.status_code == 200
    assert urgent.data["recipient_count"] == 1


def test_officer_cannot_target_another_ward():
    _ward, officer, _farmer = create_scope()
    other = Ward.objects.create(
        name="Bobasi", sub_county="Bobasi", lat=-0.79, lng=34.72
    )
    client = APIClient()
    client.force_authenticate(officer)
    response = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(other.pk),
        format="json",
    )
    assert response.status_code == 403


def test_farmer_cannot_preview_or_send_warnings():
    ward, _officer, farmer = create_scope()
    client = APIClient()
    client.force_authenticate(farmer.user)
    response = client.post(
        "/api/admin/warnings/preview/",
        warning_payload(ward.pk),
        format="json",
    )
    assert response.status_code == 403


def test_vendel_provider_success_uses_sdk_response_and_status_methods():
    client = Mock()
    client.send_sms.return_value = SendSMSResponse(
        batch_id="batch-1",
        message_ids=["message-1"],
        recipients_count=1,
        status="queued",
    )
    client.get_batch_status.return_value = BatchStatus(
        batch_id="batch-1",
        total=1,
        status_counts={"sent": 1},
        messages=[],
    )
    client.get_quota.return_value = Quota(
        plan="starter",
        sms_sent_this_month=1,
        max_sms_per_month=100,
        devices_registered=1,
        max_devices=2,
        reset_date="2026-11-01",
    )
    provider = VendelProvider(client=client)
    result = provider.send(["+254712000001"], "Test.")
    assert result["batch_id"] == "batch-1"
    assert result["message_ids"] == ["message-1"]
    assert provider.status("batch-1")["status_counts"] == {"sent": 1}
    assert provider.get_quota()["max_sms_per_month"] == 100


def test_vendel_worker_sends_successfully_with_mocked_client(monkeypatch):
    ward, officer, farmer = create_scope()
    client = Mock()
    client.send_sms.return_value = SendSMSResponse(
        batch_id="vendel-1",
        message_ids=["message-1"],
        recipients_count=1,
        status="queued",
    )
    provider = VendelProvider(client=client)
    with override_settings(SMS_PROVIDER="vendel"):
        batch = send_warning_batch(
            officer,
            warning_payload(ward.pk),
            recipients_override=None,
            enqueue=False,
        )
        monkeypatch.setattr(
            sms_service,
            "get_sms_provider",
            lambda provider_name=None: provider,
        )
        process_sms_batch.run(batch.pk)
    message = SmsMessage.objects.get(batch=batch)
    assert message.status == SmsMessage.Status.SENT
    assert message.provider_message_id == "message-1"
    assert batch.__class__.objects.get(pk=batch.pk).provider_batch_id == '["vendel-1"]'
    client.send_sms.assert_called_once_with([farmer.user.phone], "Heavy rain is expected. Check drainage and protect soil.")


def test_vendel_error_is_recorded_and_retried(monkeypatch):
    ward, officer, _farmer = create_scope()
    with override_settings(SMS_PROVIDER="vendel"):
        batch = send_warning_batch(
            officer, warning_payload(ward.pk), enqueue=False
        )

    class BrokenProvider:
        def send(self, recipients, body):
            raise RuntimeError("Vendel service is unavailable.")

    monkeypatch.setattr(
        sms_service,
        "get_sms_provider",
        lambda provider_name=None: BrokenProvider(),
    )
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(process_sms_batch, "retry", retry)
    with pytest.raises(Retry):
        process_sms_batch.run(batch.pk)
    retry.assert_called_once()
    assert retry.call_args.kwargs["countdown"] == 2
    message = SmsMessage.objects.get(batch=batch)
    assert message.status == SmsMessage.Status.FAILED
    assert "unavailable" in message.error


def test_webhook_rejects_bad_signature_and_duplicate_delivery_is_idempotent():
    ward, officer, farmer = create_scope()
    with override_settings(SMS_PROVIDER="vendel", VENDEL_WEBHOOK_SECRET="test-secret"):
        batch = send_warning_batch(
            officer,
            warning_payload(ward.pk),
            recipients_override=None,
            enqueue=False,
        )
        message = batch.messages.get()
        message.status = SmsMessage.Status.SENT
        message.provider_message_id = "message-1"
        message.save()
        batch.provider = SmsBatch.Provider.VENDEL
        batch.provider_batch_id = '["batch-1"]'
        batch.save()
        body = json.dumps(
            {
                "batch_id": "batch-1",
                "messages": [
                    {
                        "message_id": "message-1",
                        "recipient": farmer.user.phone,
                        "status": "delivered",
                    }
                ],
            },
            separators=(",", ":"),
        ).encode()
        client = APIClient()
        bad = client.generic(
            "POST",
            "/api/sms/vendel/webhook/",
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="bad",
        )
        assert bad.status_code == 403

        signature = hmac.new(
            b"test-secret", body, hashlib.sha256
        ).hexdigest()
        first = client.generic(
            "POST",
            "/api/sms/vendel/webhook/",
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
        second = client.generic(
            "POST",
            "/api/sms/vendel/webhook/",
            body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
    assert first.status_code == 200
    assert first.data["updated"] == 1
    assert second.status_code == 200
    assert second.data["updated"] == 0
    message.refresh_from_db()
    assert message.status == SmsMessage.Status.DELIVERED
    delivery = AlertDelivery.objects.get(alert=message.alert)
    assert delivery.delivered


@pytest.mark.django_db(transaction=True)
def test_retry_task_requeues_failed_messages_only(monkeypatch):
    ward, officer, farmer = create_scope()
    batch = send_warning_batch(officer, warning_payload(ward.pk), enqueue=False)
    failed = batch.messages.get()
    failed.status = SmsMessage.Status.FAILED
    failed.error = "Temporary error"
    failed.save()
    delivered_batch = SmsBatch.objects.create(
        created_by=officer,
        provider="simulator",
        template_code="sent",
        target_description="Ward: Kisii Central",
        severity="MEDIUM",
        total=1,
    )
    SmsMessage.objects.create(
        batch=delivered_batch,
        farmer=farmer,
        phone=farmer.user.phone,
        body="Already sent.",
        status=SmsMessage.Status.SENT,
    )
    queued = []
    monkeypatch.setattr(
        "gateway.sms.tasks.process_sms_batch.delay",
        lambda batch_id, message_ids=None: queued.append((batch_id, message_ids)),
    )
    retry_failed_sms.run(batch.pk, officer.pk)
    failed.refresh_from_db()
    already_sent = delivered_batch.messages.get()
    assert failed.status == SmsMessage.Status.QUEUED
    assert already_sent.status == SmsMessage.Status.SENT
    assert queued == [(batch.pk, [failed.pk])]
