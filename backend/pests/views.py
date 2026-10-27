from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from alerts.models import Rule
from common.api import ScopedModelViewSet

from advice.models import AdviceContent
from advice.services import localize_advice_content
from .models import Outbreak, PestKnowledge, PestReport, SprayLog
from .serializers import (
    OutbreakSerializer,
    PestIdentificationSerializer,
    PestKnowledgeSerializer,
    PestReportSerializer,
    PestReportVerificationSerializer,
    SprayLogSerializer,
)
from .services import identify_likely_pests, update_outbreak_for_report


class PestReportViewSet(ScopedModelViewSet):
    queryset = PestReport.objects.select_related("farmer__user", "farmer__ward", "farm", "crop")
    serializer_class = PestReportSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("ward_id",)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == User.Role.OFFICER and self.action == "list":
            queryset = queryset.filter(
                status__in=(PestReport.Status.PENDING, PestReport.Status.NEEDS_INFO)
            )
        return queryset

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.FARMER:
            raise PermissionDenied("Only farmers can submit pest reports.")
        try:
            farmer = self.request.user.farmer_profile
        except AttributeError:
            raise PermissionDenied("This account has no farmer profile.") from None
        with transaction.atomic():
            serializer.save(
                farmer=farmer,
                ward=farmer.ward,
                status=PestReport.Status.PENDING,
                verified_by=None,
                pest_name="",
                verification_note="",
            )

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE")

    @action(detail=False, methods=["get"], url_path="verification-queue")
    def verification_queue(self, request):
        if request.user.role not in (User.Role.OFFICER, User.Role.ADMIN) and not request.user.is_superuser:
            raise PermissionDenied("Only officers can view the verification queue.")
        queryset = self.get_queryset().filter(
            status__in=(PestReport.Status.PENDING, PestReport.Status.NEEDS_INFO)
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page or queryset, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="verify")
    @extend_schema(request=PestReportVerificationSerializer, responses=PestReportSerializer)
    def verify(self, request, pk=None):
        if request.user.role not in (User.Role.OFFICER, User.Role.ADMIN) and not request.user.is_superuser:
            raise PermissionDenied("Only officers can verify pest reports.")
        report = self.get_object()
        if report.status not in (PestReport.Status.PENDING, PestReport.Status.NEEDS_INFO):
            raise ValidationError({"status": "Only reports awaiting review can be verified."})
        serializer = PestReportVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        decision = data["decision"]
        status_by_decision = {
            "CONFIRM": PestReport.Status.CONFIRMED,
            "REJECT": PestReport.Status.REJECTED,
            "NEEDS_INFO": PestReport.Status.NEEDS_INFO,
            "ASK_FOR_INFO": PestReport.Status.NEEDS_INFO,
        }
        report.status = status_by_decision[decision]
        report.pest_name = data.get("pest_name", "") if decision == "CONFIRM" else ""
        report.verification_note = data.get("note", "").strip()
        report.verified_by = request.user
        report.save(
            update_fields=(
                "status",
                "pest_name",
                "verification_note",
                "verified_by",
            )
        )
        return Response(PestReportSerializer(report, context=self.get_serializer_context()).data)


class OutbreakViewSet(ScopedModelViewSet):
    queryset = Outbreak.objects.select_related("ward", "crop")
    serializer_class = OutbreakSerializer
    farmer_ward_paths = ("ward_id",)
    ward_paths = ("ward_id",)


class SprayLogViewSet(ScopedModelViewSet):
    queryset = SprayLog.objects.select_related("farm__farmer__user", "farm__farmer__ward")
    serializer_class = SprayLogSerializer
    farmer_user_paths = ("farm__farmer__user_id",)
    ward_paths = ("farm__farmer__ward_id",)

    @extend_schema(request=SprayLogSerializer, responses={201: dict})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            spray = serializer.save()
            self._ensure_scoped(spray)
        now = timezone.now()
        reentry_at = spray.sprayed_at + timedelta(hours=spray.reentry_hours)
        harvest_at = spray.sprayed_at + timedelta(days=spray.pre_harvest_days)
        checklist = localize_advice_content(
            AdviceContent.objects.get(code="PPE_CHECKLIST", active=True),
            request.user.language,
        )
        ppe_items = checklist["metadata"].get("ppe_items", {})
        checklist_items = [
            {
                "code": code,
                "name": labels.get(request.user.language) or labels.get("en", code),
                "checked": spray.ppe_checked,
            }
            for code, labels in ppe_items.items()
        ]
        payload = {
            "spray_log": self.get_serializer(spray).data,
            "checklist": checklist_items,
            "reentry_at": reentry_at,
            "reentry_remaining_seconds": max(
                0, int((reentry_at - now).total_seconds())
            ),
            "pre_harvest_interval_days": spray.pre_harvest_days,
            "harvest_allowed_at": harvest_at,
            "locked_harvest_date": timezone.localtime(harvest_at).date(),
            "harvest_locked": now < harvest_at,
        }
        headers = self.get_success_headers(serializer.data)
        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)


class PestKnowledgeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=dict)
    def get(self, request):
        language = request.query_params.get("language", "en")
        if language not in {"en", "sw", "guz"}:
            raise ValidationError({"language": "Choose en, sw, or guz."})
        serializer = PestKnowledgeSerializer(
            PestKnowledge.objects.all(),
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "guide_not_diagnosis": True,
                "results": serializer.data,
            }
        )


class PestIdentificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PestIdentificationSerializer, responses=dict)
    def post(self, request):
        serializer = PestIdentificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = request.query_params.get("language", "en")
        if language not in {"en", "sw", "guz"}:
            raise ValidationError({"language": "Choose en, sw, or guz."})
        result = identify_likely_pests(
            serializer.validated_data["symptom_icons"],
            language=language,
        )
        return Response(result)


class PestOutbreakGeoJSONView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=dict)
    def get(self, request):
        outbreaks = Outbreak.objects.select_related("ward", "crop").filter(
            confirmed_count__gte=3,
            started_at__gte=timezone.now() - timedelta(days=7),
        )
        if not request.user.is_superuser and request.user.role != User.Role.ADMIN:
            if request.user.role == User.Role.FARMER:
                outbreaks = outbreaks.filter(
                    ward_id=getattr(
                        getattr(request.user, "farmer_profile", None), "ward_id", None
                    )
                )
            elif request.user.role == User.Role.OFFICER:
                outbreaks = outbreaks.filter(ward__in=request.user.assigned_wards.all())
            else:
                outbreaks = outbreaks.none()
        features = []
        for outbreak in outbreaks:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [outbreak.ward.lng, outbreak.ward.lat],
                    },
                    "properties": {
                        "id": outbreak.pk,
                        "ward": outbreak.ward.name,
                        "pest_name": outbreak.pest_name,
                        "crop": outbreak.crop.name if outbreak.crop else None,
                        "confirmed_count": outbreak.confirmed_count,
                        "level": outbreak.level,
                        "started_at": outbreak.started_at.isoformat(),
                    },
                }
            )
        return Response(
            {"type": "FeatureCollection", "features": features},
            content_type="application/geo+json",
        )


class PestPublicStatsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=dict)
    def get(self, request):
        now = timezone.now()
        week_start = timezone.localdate(now) - timedelta(days=timezone.localdate(now).weekday())
        conditions = (
            Rule.objects.filter(code="OUTBREAK_NEARBY", active=True)
            .values_list("condition_json", flat=True)
            .first()
            or {}
        )
        days = int(conditions.get("days", 7))
        reports_this_week = PestReport.objects.filter(
            created_at__date__gte=week_start
        ).count()
        wards_on_alert = (
            Outbreak.objects.filter(
                confirmed_count__gte=int(conditions.get("confirmed_reports", 3)),
                started_at__gte=now - timedelta(days=days),
            )
            .values("ward_id")
            .distinct()
            .count()
        )
        return Response(
            {
                "reports_this_week": reports_this_week,
                "wards_on_alert": wards_on_alert,
            }
        )
