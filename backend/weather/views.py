from common.api import ScopedModelViewSet

from .models import WeatherSnapshot
from .serializers import WeatherSnapshotSerializer


class WeatherSnapshotViewSet(ScopedModelViewSet):
    queryset = WeatherSnapshot.objects.select_related("ward")
    serializer_class = WeatherSnapshotSerializer
    farmer_ward_paths = ("ward_id",)
    ward_paths = ("ward_id",)
