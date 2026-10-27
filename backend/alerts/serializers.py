from rest_framework import serializers

from .models import Alert, AlertDelivery, Rule


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = "__all__"


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = "__all__"
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        farmer = attrs.get("farmer", getattr(self.instance, "farmer", None))
        farm = attrs.get("farm", getattr(self.instance, "farm", None))
        if farm and farmer and farm.farmer_id != farmer.pk:
            raise serializers.ValidationError({"farm": "The farm must belong to the selected farmer."})
        return attrs


class AlertDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertDelivery
        fields = "__all__"


class AlertFeedbackSerializer(serializers.Serializer):
    feedback = serializers.ChoiceField(choices=AlertDelivery.Feedback.choices)

