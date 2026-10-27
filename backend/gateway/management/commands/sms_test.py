from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from gateway.sms.providers import get_sms_provider
from gateway.sms.service import send_warning_batch
from gateway.sms.tasks import process_sms_batch


class Command(BaseCommand):
    help = "Send one explicit SMS test to a Kenyan E.164 recipient."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Recipient in E.164 format.")

    def handle(self, *args, **options):
        admin = User.objects.filter(
            role=User.Role.ADMIN, is_active=True
        ).order_by("pk").first()
        if admin is None:
            raise CommandError("Create an active ADMIN account before running sms_test.")

        payload = {
            "template_code": "safe_reentry",
            "language": "en",
            "severity": "MEDIUM",
            "target": {"type": "demo"},
            "message": "SHAMBA SMS test. This confirms your configured SMS provider.",
        }
        try:
            batch = send_warning_batch(
                admin,
                payload,
                recipients_override=[options["to"]],
                enqueue=False,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        result = process_sms_batch.apply(args=(batch.pk,), throw=False)
        batch.refresh_from_db()
        try:
            quota = get_sms_provider().get_quota()
        except Exception as exc:
            quota = f"Unavailable: {exc}"
        self.stdout.write(f"Batch ID: {batch.pk}")
        self.stdout.write(f"Provider: {batch.provider}")
        self.stdout.write(f"Quota: {quota}")
        if result.failed() or batch.messages.filter(status="FAILED").exists():
            message = batch.messages.filter(status="FAILED").first()
            raise CommandError(
                f"SMS test failed: {message.error if message else result.result}"
            )
