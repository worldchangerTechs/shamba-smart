from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import PestReport
from .services import update_outbreak_for_report


@receiver(pre_save, sender=PestReport, dispatch_uid="remember-pest-report-status")
def remember_pest_report_status(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
    else:
        instance._previous_status = None


@receiver(post_save, sender=PestReport, dispatch_uid="update-confirmed-pest-outbreak")
def update_confirmed_pest_outbreak(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_previous_status", None)
    if (
        instance.status == PestReport.Status.CONFIRMED
        and previous_status != PestReport.Status.CONFIRMED
    ):
        update_outbreak_for_report(instance)
