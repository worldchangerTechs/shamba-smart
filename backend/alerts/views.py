from django.db import transaction
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.models import User
from common.api import PublicReadOnlyViewSet, ScopedModelViewSet

from .engine import record_rule_feedback
from .models import Alert, AlertDelivery, Rule
from .serializers import (
    AlertDeliverySerializer,
    AlertFeedbackSerializer,
    AlertSerializer,
    RuleSerializer,
)


class RuleViewSet(PublicReadOnlyViewSet):
    queryset = Rule.objects.all()
    serializer_class = RuleSerializer


class AlertViewSet(ScopedModelViewSet):
    queryset = Alert.objects.select_related("farmer__user", "farmer__ward", "farm", "rule")
    serializer_class = AlertSerializer
    farmer_user_paths = ("farmer__user_id",)
    ward_paths = ("farmer__ward_id",)


class AlertDeliveryViewSet(ScopedModelViewSet):
    queryset = AlertDelivery.objects.select_related("alert__farmer__user", "alert__farmer__ward")
    serializer_class = AlertDeliverySerializer
    farmer_user_paths = ("alert__farmer__user_id",)
    ward_paths = ("alert__farmer__ward_id",)

    def create(self, request, *args, **kwargs):
        raise PermissionDenied("Alert deliveries are created by the warning service.")

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Submit delivery feedback using the feedback action.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Submit delivery feedback using the feedback action.")

    @action(detail=True, methods=["post"], url_path="feedback")
    def feedback(self, request, pk=None):
        delivery = self.get_object()
        if (
            request.user.role != User.Role.ADMIN
            and not request.user.is_superuser
            and (
                request.user.role != User.Role.FARMER
                or delivery.alert.farmer.user_id != request.user.pk
            )
        ):
            raise PermissionDenied("Only the alert recipient can submit feedback.")
        serializer = AlertFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            delivery.feedback = serializer.validated_data["feedback"]
            delivery.save(update_fields=["feedback"])
            record_rule_feedback(delivery)
        return Response(AlertDeliverySerializer(delivery).data)
