from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator

from accounts.models import Farmer


class Lesson(models.Model):
    class ProblemTag(models.TextChoices):
        EROSION = "erosion", "Erosion"
        PESTS = "pests", "Pests"
        PPE = "ppe", "Spray safety"
        SOIL = "soil", "Soil fertility"
        CLIMATE = "climate", "Climate"
        MARKET = "market", "Markets"
        WASTE = "waste", "Waste management"
        PLANTING = "planting", "Planting"

    title = models.CharField(max_length=200)
    title_by_language = models.JSONField(default=dict, blank=True)
    problem_tag = models.CharField(max_length=80, choices=ProblemTag.choices, db_index=True)
    body_by_language = models.JSONField(default=dict)
    audio_url = models.URLField(blank=True)
    audio_en = models.FileField(upload_to="academy/audio/en/", blank=True)
    audio_sw = models.FileField(upload_to="academy/audio/sw/", blank=True)
    audio_guz = models.FileField(upload_to="academy/audio/guz/", blank=True)
    photo = models.ImageField(upload_to="academy/lessons/", blank=True, null=True)
    quiz_by_language = models.JSONField(default=dict, blank=True)
    tip_by_language = models.JSONField(default=dict, blank=True)
    duration_sec = models.PositiveIntegerField(validators=[MaxValueValidator(120)])
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class LessonProgress(models.Model):
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    completed = models.BooleanField(default=False)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    completed_steps = models.PositiveSmallIntegerField(default=0)
    quiz_score = models.PositiveSmallIntegerField(null=True, blank=True)
    quiz_answers = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["farmer", "lesson"], name="unique_farmer_lesson_progress")
        ]


class Badge(models.Model):
    class BadgeCode(models.TextChoices):
        SOIL_HERO = "SOIL_HERO", "Soil Hero"
        SAFE_SPRAYER = "SAFE_SPRAYER", "Safe Sprayer"
        EROSION_FIGHTER = "EROSION_FIGHTER", "Erosion Fighter"
        CLEAN_FARM = "CLEAN_FARM", "Clean Farm"
        MARKET_READY = "MARKET_READY", "Market Ready"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="badges")
    code = models.CharField(
        max_length=20, choices=BadgeCode.choices, default=BadgeCode.SOIL_HERO
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["farmer", "name"], name="unique_farmer_badge"),
            models.UniqueConstraint(fields=["farmer", "code"], name="unique_farmer_badge_code"),
        ]


class OfficerQuestion(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ANSWERED = "ANSWERED", "Answered"

    farmer = models.ForeignKey(
        Farmer, on_delete=models.CASCADE, related_name="officer_questions"
    )
    ward = models.ForeignKey(
        "accounts.Ward", on_delete=models.PROTECT, related_name="officer_questions"
    )
    question = models.TextField(blank=True)
    voice_note = models.FileField(
        upload_to="academy/questions/%Y/%m/", blank=True, null=True
    )
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    answer = models.TextField(blank=True)
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="answered_farmer_questions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]


class FrequentlyAskedQuestion(models.Model):
    question = models.TextField()
    answer = models.TextField()
    language = models.CharField(
        max_length=3,
        choices=(("en", "English"), ("sw", "Kiswahili"), ("guz", "Ekegusii")),
        default="en",
        db_index=True,
    )
    source_question = models.OneToOneField(
        OfficerQuestion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="faq_entry",
    )
    search_terms = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class WeeklyTipDelivery(models.Model):
    farmer = models.ForeignKey(
        Farmer, on_delete=models.CASCADE, related_name="weekly_tip_deliveries"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="tip_deliveries"
    )
    week_start = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField(default=False)
    provider_response = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["farmer", "week_start"], name="unique_farmer_weekly_tip"
            )
        ]
