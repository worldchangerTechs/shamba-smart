from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from alerts.tasks import alert_for_spray_log
from pests.models import SprayLog


@receiver(post_save, sender=SprayLog, dispatch_uid="queue-spray-safety-alert")
def queue_spray_safety_alert(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(
            lambda: alert_for_spray_log.delay(instance.pk)
        )
