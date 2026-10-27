from django.conf import settings
from django.core.management.base import BaseCommand

from gateway.sms.providers import get_sms_provider


class Command(BaseCommand):
    help = "Show the active SMS provider, base URL and current quota."

    def handle(self, *args, **options):
        self.stdout.write(f"Provider: {settings.SMS_PROVIDER}")
        self.stdout.write(
            f"Base URL: {settings.VENDEL_BASE_URL if settings.SMS_PROVIDER == 'vendel' else 'not used'}"
        )
        try:
            quota = get_sms_provider().get_quota()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Quota unavailable: {exc}"))
            return
        self.stdout.write(f"Quota: {quota}")
