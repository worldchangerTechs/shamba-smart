from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from drf_spectacular.utils import OpenApiParameter, extend_schema

from accounts.models import User
from common.api import ScopedModelViewSet

from .models import AdviceContent, AdviceRecommendation
from .serializers import (
    AdviceContentSerializer,
    AdviceRecommendationSerializer,
    MteremkoGuardInputSerializer,
    PpeGapInputSerializer,
    TakaLoopInputSerializer,
    UdongoDoctorInputSerializer,
)
from .services import (
    get_farm_for_user,
    mteremko_guard,
    ppe_gap_finder,
    taka_loop,
    udongo_doctor,
)


class AdviceRecommendationViewSet(ScopedModelViewSet):
    queryset = AdviceRecommendation.objects.select_related("farmer__user", "farmer__ward", "farm")
    serializer_class = AdviceRecommendationSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)

    def _farmer(self):
        if self.request.user.role != User.Role.FARMER:
            raise PermissionDenied("This service is available to farmer accounts.")
        try:
            return self.request.user.farmer_profile
        except AttributeError:
            raise PermissionDenied("This account has no farmer profile.") from None

    @action(detail=False, methods=["post"], url_path="udongo-doctor")
    @extend_schema(request=UdongoDoctorInputSerializer, responses=dict)
    def udongo_doctor(self, request):
        serializer = UdongoDoctorInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get("farm_id"):
            get_farm_for_user(request.user, data["farm_id"])
        result = udongo_doctor(
            crop_name=data["crop"],
            soil_ph=data.get("soil_ph"),
            quiz=data.get("quiz"),
            language=request.user.language,
        )
        return Response(result)

    @action(detail=False, methods=["post"], url_path="mteremko-guard")
    @extend_schema(request=MteremkoGuardInputSerializer, responses=dict)
    def mteremko_guard(self, request):
        serializer = MteremkoGuardInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        farm = get_farm_for_user(request.user, data["farm_id"])
        return Response(
            mteremko_guard(
                farm=farm,
                ground_cover_percent=data["ground_cover_percent"],
                tillage=data["tillage"],
                language=request.user.language,
            )
        )

    @action(detail=False, methods=["post"], url_path="ppe-gap-finder")
    @extend_schema(request=PpeGapInputSerializer, responses=dict)
    def ppe_gap_finder(self, request):
        farmer = self._farmer()
        serializer = PpeGapInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        farm = (
            get_farm_for_user(request.user, data["farm_id"])
            if data.get("farm_id")
            else None
        )
        return Response(
            ppe_gap_finder(
                farmer=farmer,
                owned_items=data["owned_items"],
                farm=farm,
                language=request.user.language,
            )
        )

    @action(detail=False, methods=["get"], url_path="taka-loop")
    @extend_schema(
        parameters=[
            OpenApiParameter("waste_type", str, required=True),
            OpenApiParameter("farm_id", int, required=False),
        ],
        responses=dict,
    )
    def taka_loop(self, request):
        farmer = self._farmer()
        serializer = TakaLoopInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        farm = (
            get_farm_for_user(request.user, data["farm_id"])
            if data.get("farm_id")
            else None
        )
        return Response(
            taka_loop(
                farmer=farmer,
                waste_type=data["waste_type"],
                farm=farm,
                language=request.user.language,
            )
        )


class AdviceContentViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = AdviceContent.objects.filter(active=True)
    serializer_class = AdviceContentSerializer
