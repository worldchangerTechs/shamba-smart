from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema
from weather.models import WeatherSnapshot
from weather.serializers import WeatherSnapshotSerializer
from weather.services.mvua_planner import planner_for_farm

from common.api import PublicReadOnlyViewSet, ScopedModelViewSet

from .models import Crop, Farm, Planting
from .serializers import CropSerializer, FarmSerializer, PlantingSerializer


class CropViewSet(PublicReadOnlyViewSet):
    queryset = Crop.objects.all()
    serializer_class = CropSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()


class FarmViewSet(ScopedModelViewSet):
    queryset = Farm.objects.select_related("farmer__user", "farmer__ward")
    serializer_class = FarmSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)

    @extend_schema(responses=dict)
    @action(detail=True, methods=["get"], url_path="planner")
    def planner(self, request, pk=None):
        farm = self.get_object()
        return Response(planner_for_farm(farm))

    @extend_schema(responses=WeatherSnapshotSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="weather")
    def weather(self, request, pk=None):
        farm = self.get_object()
        today = timezone.localdate()
        snapshots = WeatherSnapshot.objects.filter(
            ward=farm.farmer.ward,
            date__gte=today - timedelta(days=30),
            date__lte=today + timedelta(days=13),
        ).order_by("date")
        return Response(WeatherSnapshotSerializer(snapshots, many=True).data)


class PlantingViewSet(ScopedModelViewSet):
    queryset = Planting.objects.select_related("farm__farmer__user", "crop")
    serializer_class = PlantingSerializer
    farmer_user_paths = ("farm__farmer__user_id",)
    ward_paths = ("farm__farmer__ward_id",)
