from datetime import datetime, timedelta

from celery import shared_task
from django.utils import timezone

from accounts.models import Farmer
from alerts.models import Alert, Rule

from .models import Lesson


def _weekly_tip_lesson(now):
    lessons = Lesson.objects.filter(active=True).order_by("pk")
    count = lessons.count()
    if not count:
        return None
    iso_year, iso_week, _weekday = now.isocalendar()
    return lessons[(iso_year * 53 + iso_week) % count]


def _tip_text(lesson, language):
    localized = lesson.tip_by_language.get(language) or lesson.tip_by_language.get("en")
    if not localized:
        steps = lesson.body_by_language.get(language) or lesson.body_by_language.get("en", [])
        localized = steps[0] if steps else lesson.title
    return f"Shamba Tip: {localized}"[:160]


@shared_task
def send_weekly_tips(now_iso=None):
    """Create app-feed tip Alerts; SMS delivery requires a manual admin action."""
    now = datetime.fromisoformat(now_iso) if now_iso else timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    lesson = _weekly_tip_lesson(now)
    if lesson is None:
        return {"alerts_created": 0, "reason": "no_active_lessons"}

    week_start = timezone.localdate(now) - timedelta(
        days=timezone.localdate(now).weekday()
    )
    rule, _ = Rule.objects.get_or_create(
        code="ACADEMY_WEEKLY_TIP",
        defaults={
            "problem_tag": lesson.problem_tag,
            "severity": Rule.Severity.LOW,
            "message_templates": {},
            "cooldown_hours": 0,
            "active": True,
        },
    )
    created = 0
    for farmer in Farmer.objects.filter(user__is_active=True).iterator():
        _, was_created = Alert.objects.get_or_create(
            farmer=farmer,
            rule=rule,
            source_key=f"weekly-tip:{week_start}:{lesson.pk}",
            defaults={
                "severity": Rule.Severity.LOW,
                "title": "Shamba Tip of the Week",
                "body_by_language": {
                    language: _tip_text(lesson, language)
                    for language in ("en", "sw", "guz")
                },
            },
        )
        created += int(was_created)
    return {
        "alerts_created": created,
        "sent": 0,
        "week_start": week_start.isoformat(),
    }
