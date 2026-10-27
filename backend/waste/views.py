from django.db import transaction
from common.api import PublicReadOnlyViewSet, ScopedModelViewSet
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from accounts.models import User
from .models import DisposalPoint, WasteLog
from .serializers import DisposalPointSerializer, WasteLogSerializer


class WasteLogViewSet(ScopedModelViewSet):
    queryset = WasteLog.objects.select_related("farmer__user", "farmer__ward")
    serializer_class = WasteLogSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)

    @extend_schema(responses={201: dict})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if request.user.role == User.Role.FARMER:
                instance = serializer.save(farmer=request.user.farmer_profile)
            else:
                instance = serializer.save()
            self._ensure_scoped(instance)
        farmer = instance.farmer
        from academy.views import award_clean_farm_badge

        award_clean_farm_badge(farmer)
        action_count = WasteLog.objects.filter(farmer=farmer).count()
        payload = {
            **self.get_serializer(instance).data,
            "clean_farm": {
                "waste_action_count": action_count,
                "score": min(100, action_count * 10),
                "score_per_logged_action": 10,
            },
        }
        return Response(payload, status=status.HTTP_201_CREATED)


class DisposalPointViewSet(PublicReadOnlyViewSet):
    queryset = DisposalPoint.objects.select_related("ward")
    serializer_class = DisposalPointSerializer
