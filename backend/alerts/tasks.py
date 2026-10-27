from celery import shared_task

from alerts.engine import evaluate_rules, evaluate_spray_log


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def evaluate_alert_rules(self):
    alerts = evaluate_rules()
    return {"alerts_created": len(alerts)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def alert_for_spray_log(self, spray_log_id):
    from pests.models import SprayLog

    spray = SprayLog.objects.select_related("farm__farmer__user", "farm__farmer__ward").get(
        pk=spray_log_id
    )
    alerts = evaluate_spray_log(spray)
    return {"alerts_created": len(alerts)}
