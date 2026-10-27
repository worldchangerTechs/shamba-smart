from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from accounts.models import User
from .models import (
    Badge,
    FrequentlyAskedQuestion,
    Lesson,
    LessonProgress,
    OfficerQuestion,
)


class LessonSerializer(serializers.ModelSerializer):
    steps = serializers.SerializerMethodField()
    quiz = serializers.SerializerMethodField()
    audio_by_language = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "title_by_language",
            "problem_tag",
            "duration_sec",
            "steps",
            "quiz",
            "audio_by_language",
            "audio_url",
            "photo",
            "tip_by_language",
        )

    def _language(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "language", "en")

    def get_steps(self, obj) -> list[str]:
        steps = obj.body_by_language.get(self._language()) or obj.body_by_language.get("en", [])
        return steps

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        language = self._language()
        representation["title"] = (
            instance.title_by_language.get(language)
            or instance.title_by_language.get("en")
            or instance.title
        )
        return representation

    @extend_schema_field(
        serializers.ListField(child=serializers.DictField())
    )
    def get_quiz(self, obj):
        quiz = obj.quiz_by_language.get(self._language()) or obj.quiz_by_language.get("en", [])
        return [
            {
                "question": item["question"],
                "options": item["options"],
            }
            for item in quiz
        ]

    def get_audio_by_language(self, obj) -> dict[str, str]:
        return {
            language: getattr(obj, f"audio_{language}").url
            if getattr(obj, f"audio_{language}")
            else ""
            for language in ("en", "sw", "guz")
        }


class LessonProgressReadSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)

    class Meta:
        model = LessonProgress
        fields = (
            "id",
            "farmer",
            "lesson",
            "lesson_title",
            "completed",
            "progress_percent",
            "completed_steps",
            "quiz_score",
            "started_at",
            "completed_at",
        )
        read_only_fields = fields


class LessonProgressUpdateSerializer(serializers.Serializer):
    completed_steps = serializers.IntegerField(min_value=0, max_value=5, required=False)
    quiz_answers = serializers.ListField(
        child=serializers.IntegerField(min_value=0), min_length=3, max_length=3, required=False
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide completed_steps or quiz_answers.")
        return attrs


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = "__all__"
        read_only_fields = ("awarded_at", "farmer", "code", "name", "description")


class OfficerQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficerQuestion
        fields = (
            "id",
            "farmer",
            "ward",
            "question",
            "voice_note",
            "status",
            "answer",
            "answered_by",
            "created_at",
            "answered_at",
        )
        read_only_fields = (
            "farmer",
            "ward",
            "status",
            "answer",
            "answered_by",
            "created_at",
            "answered_at",
        )

    def validate(self, attrs):
        question = attrs.get("question", "").strip()
        voice_note = attrs.get("voice_note")
        if not question and not voice_note:
            raise serializers.ValidationError(
                "Provide question text or attach a voice note."
            )
        if self.instance is None and self.context["request"].user.role != User.Role.FARMER:
            raise serializers.ValidationError("Only farmers can submit questions.")
        return attrs


class OfficerAnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(min_length=2, max_length=5000)
    language = serializers.ChoiceField(
        choices=("en", "sw", "guz"), required=False, default="en"
    )


class FrequentlyAskedQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FrequentlyAskedQuestion
        fields = ("id", "question", "answer", "language", "search_terms", "created_at")
        read_only_fields = fields
