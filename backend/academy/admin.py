from django.contrib import admin

from .models import (
    Badge,
    FrequentlyAskedQuestion,
    Lesson,
    LessonProgress,
    OfficerQuestion,
    WeeklyTipDelivery,
)

admin.site.register(
    (
        Lesson,
        LessonProgress,
        Badge,
        OfficerQuestion,
        FrequentlyAskedQuestion,
        WeeklyTipDelivery,
    )
)
