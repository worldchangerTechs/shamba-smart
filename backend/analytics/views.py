from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from accounts.models import Farmer, User
from alerts.models import Alert
from farms.models import Farm
from pests.models import PestReport


class SummarySerializer(serializers.Serializer):
    farmers = serializers.IntegerField()
    farms = serializers.IntegerField()
    open_alerts = serializers.IntegerField()
    pending_pest_reports = serializers.IntegerField()


class SummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SummarySerializer)
    def get(self, request):
        farmers = Farmer.objects.all()
        farms = Farm.objects.all()
        alerts = Alert.objects.all()
        pest_reports = PestReport.objects.all()
        user = request.user

        if not user.is_superuser and user.role != User.Role.ADMIN:
            if user.role == User.Role.FARMER:
                farmers = farmers.filter(user=user)
                farms = farms.filter(farmer__user=user)
                alerts = alerts.filter(farmer__user=user)
                pest_reports = pest_reports.filter(farmer__user=user)
            elif user.role == User.Role.OFFICER:
                ward_ids = user.assigned_wards.values_list("pk", flat=True)
                farmers = farmers.filter(ward_id__in=ward_ids)
                farms = farms.filter(farmer__ward_id__in=ward_ids)
                alerts = alerts.filter(farmer__ward_id__in=ward_ids)
                pest_reports = pest_reports.filter(ward_id__in=ward_ids)
            else:
                return Response(
                    {"farmers": 0, "farms": 0, "open_alerts": 0, "pending_pest_reports": 0}
                )

        return Response(
            {
                "farmers": farmers.count(),
                "farms": farms.count(),
                "open_alerts": alerts.filter(status=Alert.Status.OPEN).count(),
                "pending_pest_reports": pest_reports.filter(
                    status=PestReport.Status.PENDING
                ).count(),
            }
        )
