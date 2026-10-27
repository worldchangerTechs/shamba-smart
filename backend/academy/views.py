from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.models import Farmer, User
from common.api import PublicReadOnlyViewSet, ScopedModelViewSet
from waste.models import WasteLog
from .models import (
    Badge,
    FrequentlyAskedQuestion,
    Lesson,
    LessonProgress,
    OfficerQuestion,
)
from .serializers import (
    BadgeSerializer,
    FrequentlyAskedQuestionSerializer,
    LessonProgressReadSerializer,
    LessonProgressUpdateSerializer,
    LessonSerializer,
    OfficerAnswerSerializer,
    OfficerQuestionSerializer,
)

BADGE_FOR_TAG = {
    Lesson.ProblemTag.SOIL: (Badge.BadgeCode.SOIL_HERO, "Soil Hero"),
    Lesson.ProblemTag.PPE: (Badge.BadgeCode.SAFE_SPRAYER, "Safe Sprayer"),
    Lesson.ProblemTag.EROSION: (Badge.BadgeCode.EROSION_FIGHTER, "Erosion Fighter"),
    Lesson.ProblemTag.MARKET: (Badge.BadgeCode.MARKET_READY, "Market Ready"),
}


def _farmer_for_user(user):
    if user.role != User.Role.FARMER:
        raise PermissionDenied("This action is available to farmer accounts.")
    try:
        return user.farmer_profile
    except Farmer.DoesNotExist:
        raise PermissionDenied("This account has no farmer profile.") from None


def _award_badge(farmer, code, name, description):
    Badge.objects.get_or_create(
        farmer=farmer,
        code=code,
        defaults={"name": name, "description": description},
    )


def _award_lesson_badges(farmer, lesson):
    badge_data = BADGE_FOR_TAG.get(lesson.problem_tag)
    if badge_data:
        completed_count = LessonProgress.objects.filter(
            farmer=farmer,
            lesson__problem_tag=lesson.problem_tag,
            completed=True,
        ).count()
        if completed_count >= 2:
            code, name = badge_data
            _award_badge(
                farmer,
                code,
                name,
                f"Completed two {lesson.get_problem_tag_display().lower()} lessons.",
            )
    award_clean_farm_badge(farmer)


def award_clean_farm_badge(farmer):
    if WasteLog.objects.filter(farmer=farmer).count() >= 5:
        _award_badge(
            farmer,
            Badge.BadgeCode.CLEAN_FARM,
            "Clean Farm",
            "Logged five or more safe farm-waste actions.",
        )


class LessonViewSet(PublicReadOnlyViewSet):
    queryset = Lesson.objects.filter(active=True)
    serializer_class = LessonSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        tag = self.request.query_params.get("problem_tag")
        if tag:
            queryset = queryset.filter(problem_tag=tag)
        return queryset


class LessonProgressViewSet(ScopedModelViewSet):
    queryset = LessonProgress.objects.select_related(
        "farmer__user", "farmer__ward", "lesson"
    )
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return LessonProgressReadSerializer
        return LessonProgressUpdateSerializer

    def create(self, request, *args, **kwargs):
        farmer = _farmer_for_user(request.user)
        lesson_id = request.data.get("lesson")
        lesson = get_object_or_404(Lesson, pk=lesson_id, active=True)
        serializer = LessonProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        progress, created = LessonProgress.objects.get_or_create(
            farmer=farmer, lesson=lesson
        )
        return self._update_progress(progress, serializer.validated_data, created)

    def partial_update(self, request, *args, **kwargs):
        farmer = _farmer_for_user(request.user)
        progress = get_object_or_404(
            LessonProgress.objects.select_related("lesson"),
            pk=kwargs["pk"],
            farmer=farmer,
        )
        serializer = LessonProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._update_progress(progress, serializer.validated_data)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT")

    def _update_progress(self, progress, data, created=False):
        with transaction.atomic():
            steps = data.get("completed_steps", progress.completed_steps)
            steps = max(progress.completed_steps, steps)
            progress.completed_steps = steps
            progress.progress_percent = steps * 20
            if "quiz_answers" in data:
                quiz = progress.lesson.quiz_by_language.get(
                    progress.farmer.user.language
                ) or progress.lesson.quiz_by_language.get("en", [])
                if len(quiz) != 3:
                    raise ValidationError(
                        "This lesson does not have a valid three-question quiz."
                    )
                answers = data["quiz_answers"]
                if len(answers) != 3:
                    raise ValidationError({"quiz_answers": "Answer all 3 questions."})
                if any(answer >= len(quiz[index]["options"]) for index, answer in enumerate(answers)):
                    raise ValidationError(
                        {"quiz_answers": "An answer is outside the available choices."}
                    )
                progress.quiz_answers = answers
                progress.quiz_score = sum(
                    answer == item["answer_index"]
                    for answer, item in zip(answers, quiz)
                )
                if progress.quiz_score == 3:
                    progress.completed_steps = 5
                    progress.progress_percent = 100
                    progress.completed = True
                    progress.completed_at = progress.completed_at or timezone.now()
            progress.save()
            if progress.completed:
                _award_lesson_badges(progress.farmer, progress.lesson)
        response = LessonProgressReadSerializer(
            progress, context={"request": self.request}
        )
        return Response(
            response.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BadgeViewSet(ScopedModelViewSet):
    queryset = Badge.objects.select_related("farmer__user", "farmer__ward")
    serializer_class = BadgeSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)
    http_method_names = ("get", "head", "options")


class OfficerQuestionViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = OfficerQuestion.objects.select_related(
        "farmer__user", "farmer__ward", "answered_by"
    )
    serializer_class = OfficerQuestionSerializer
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            queryset = super().get_queryset()
        elif user.role == User.Role.OFFICER:
            queryset = super().get_queryset().filter(
                ward__in=user.assigned_wards.all()
            )
        elif user.role == User.Role.FARMER:
            queryset = super().get_queryset().filter(farmer__user=user)
        else:
            queryset = super().get_queryset().none()
        if self.action == "list" and user.role == User.Role.OFFICER:
            return queryset.filter(status=OfficerQuestion.Status.OPEN)
        return queryset

    def create(self, request, *args, **kwargs):
        farmer = _farmer_for_user(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save(farmer=farmer, ward=farmer.ward)
        return Response(
            self.get_serializer(question).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"], url_path="queue")
    def queue(self, request):
        if request.user.role not in (User.Role.OFFICER, User.Role.ADMIN) and not request.user.is_superuser:
            raise PermissionDenied("Only officers can view the question queue.")
        queryset = self.get_queryset().filter(status=OfficerQuestion.Status.OPEN)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page or queryset, many=True)
        return (
            self.get_paginated_response(serializer.data)
            if page is not None
            else Response(serializer.data)
        )

    @action(detail=True, methods=["post"], url_path="answer")
    @extend_schema(request=OfficerAnswerSerializer, responses=OfficerQuestionSerializer)
    def answer(self, request, pk=None):
        if request.user.role not in (User.Role.OFFICER, User.Role.ADMIN) and not request.user.is_superuser:
            raise PermissionDenied("Only an officer can answer farmer questions.")
        question = self.get_object()
        if question.status == OfficerQuestion.Status.ANSWERED:
            raise ValidationError({"status": "This question has already been answered."})
        serializer = OfficerAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            question.answer = data["answer"].strip()
            question.answered_by = request.user
            question.answered_at = timezone.now()
            question.status = OfficerQuestion.Status.ANSWERED
            question.save(
                update_fields=("answer", "answered_by", "answered_at", "status")
            )
            FrequentlyAskedQuestion.objects.create(
                question=question.question or f"Voice question from {question.ward.name}",
                answer=question.answer,
                language=data["language"],
                source_question=question,
                search_terms=" ".join(
                    (question.question + " " + question.answer).casefold().split()
                ),
            )
        return Response(
            OfficerQuestionSerializer(
                question, context=self.get_serializer_context()
            ).data
        )


class FrequentlyAskedQuestionViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = FrequentlyAskedQuestion.objects.all()
    serializer_class = FrequentlyAskedQuestionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        language = self.request.query_params.get("language")
        query = self.request.query_params.get("q", "").strip()
        if language:
            queryset = queryset.filter(language=language)
        if query:
            for word in query.split():
                queryset = queryset.filter(
                    Q(question__icontains=word)
                    | Q(answer__icontains=word)
                    | Q(search_terms__icontains=word)
                )
        return queryset

