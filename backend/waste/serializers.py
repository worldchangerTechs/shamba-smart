from rest_framework import serializers

from accounts.models import User
from .models import DisposalPoint, WasteLog


class WasteLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteLog
        fields = "__all__"
        read_only_fields = ("logged_at",)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if request.user.role == User.Role.FARMER:
                fields["farmer"].read_only = True
        return fields

    def validate(self, attrs):
        request = self.context.get("request")
        farmer = attrs.get("farmer", getattr(self.instance, "farmer", None))
        if farmer is None and request and request.user.role == User.Role.FARMER:
            farmer = getattr(request.user, "farmer_profile", None)
        spray_log = attrs.get("spray_log", getattr(self.instance, "spray_log", None))
        if spray_log and farmer and spray_log.farm.farmer_id != farmer.pk:
            raise serializers.ValidationError(
                {"spray_log": "The spray log must belong to the selected farmer."}
            )
        return attrs


class DisposalPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisposalPoint
        fields = "__all__"
