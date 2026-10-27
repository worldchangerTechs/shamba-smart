from rest_framework import serializers

from accounts.models import User
from .models import Outbreak, PestKnowledge, PestReport, SprayLog


SYMPTOM_ICON_CHOICES = (
    "leaf_holes",
    "frass",
    "aphid_clusters",
    "sticky_leaves",
    "whitefly_cloud",
    "leafminer_tunnels",
    "dark_leaf_spots",
    "white_leaf_growth",
    "dark_fruit_lesions",
    "berry_drop",
)


class PestReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PestReport
        fields = "__all__"
        read_only_fields = (
            "created_at",
            "status",
            "verified_by",
            "pest_name",
            "verification_note",
            "farmer",
            "ward",
        )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if self.instance is None and request.method == "POST":
                fields["photo"].required = True
        return fields

    def validate_lat(self, value):
        if value is not None and not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_lng(self, value):
        if value is not None and not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        farmer = attrs.get("farmer", getattr(self.instance, "farmer", None))
        if farmer is None and request and request.user.role == User.Role.FARMER:
            farmer = getattr(request.user, "farmer_profile", None)
        farm = attrs.get("farm", getattr(self.instance, "farm", None))
        ward = attrs.get("ward", getattr(self.instance, "ward", None))
        if farmer and farm and farm.farmer_id != farmer.pk:
            raise serializers.ValidationError({"farm": "The farm must belong to the selected farmer."})
        if farmer and ward and ward.pk != farmer.ward_id:
            raise serializers.ValidationError({"ward": "The report ward must match the farmer's ward."})
        if self.instance is None:
            if attrs.get("crop") is None:
                raise serializers.ValidationError({"crop": "Select the affected crop."})
            if (attrs.get("lat") is None) != (attrs.get("lng") is None):
                raise serializers.ValidationError("Provide both lat and lng, or neither.")
            farm = attrs.get("farm")
            if farm:
                if attrs.get("lat") is None:
                    attrs["lat"] = farm.lat
                if attrs.get("lng") is None:
                    attrs["lng"] = farm.lng
            elif attrs.get("lat") is None:
                raise serializers.ValidationError(
                    {"location": "Provide device coordinates or select one of your farms."}
                )
        return attrs


class PestReportVerificationSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=("CONFIRM", "REJECT", "NEEDS_INFO", "ASK_FOR_INFO")
    )
    pest_name = serializers.ChoiceField(
        choices=PestReport.PestName.choices, required=False
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        decision = attrs["decision"]
        if decision == "CONFIRM" and not attrs.get("pest_name"):
            raise serializers.ValidationError(
                {"pest_name": "Choose the confirmed pest from the pest list."}
            )
        if decision in {"NEEDS_INFO", "ASK_FOR_INFO"} and not attrs.get("note", "").strip():
            raise serializers.ValidationError(
                {"note": "Explain what additional information is needed."}
            )
        return attrs


class PestIdentificationSerializer(serializers.Serializer):
    symptom_icons = serializers.ListField(
        child=serializers.ChoiceField(choices=SYMPTOM_ICON_CHOICES),
        min_length=3,
        max_length=3,
    )

    def validate_symptom_icons(self, value):
        if len(set(value)) != 3:
            raise serializers.ValidationError("Choose three different symptom icons.")
        return value


class PestKnowledgeSerializer(serializers.ModelSerializer):
    pest_label = serializers.CharField(source="get_pest_name_display", read_only=True)
    symptoms = serializers.SerializerMethodField()
    safe_first_actions = serializers.SerializerMethodField()
    integrated_pest_management = serializers.SerializerMethodField()
    when_to_call_an_officer = serializers.SerializerMethodField()

    class Meta:
        model = PestKnowledge
        fields = (
            "pest_name",
            "pest_label",
            "symptom_icons",
            "photo",
            "symptoms",
            "safe_first_actions",
            "integrated_pest_management",
            "when_to_call_an_officer",
        )

    def _localized(self, obj, field):
        language = self.context.get("request").query_params.get("language", "en")
        values = getattr(obj, field)
        return values.get(language) or values.get("en", [])

    def get_symptoms(self, obj) -> list[str]:
        return self._localized(obj, "symptoms_by_language")

    def get_safe_first_actions(self, obj) -> list[str]:
        return self._localized(obj, "safe_actions_by_language")

    def get_integrated_pest_management(self, obj) -> list[str]:
        return self._localized(obj, "ipm_by_language")

    def get_when_to_call_an_officer(self, obj) -> list[str]:
        return self._localized(obj, "call_officer_by_language")


class OutbreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outbreak
        fields = "__all__"


class SprayLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SprayLog
        fields = "__all__"

    def validate_farm(self, farm):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return farm
        user = request.user
        if user.role == User.Role.FARMER:
            if farm.farmer.user_id != user.pk:
                raise serializers.ValidationError("The farm must belong to you.")
        elif user.role == User.Role.OFFICER:
            if not user.assigned_wards.filter(pk=farm.farmer.ward_id).exists():
                raise serializers.ValidationError(
                    "The farm must be in one of your assigned wards."
                )
        return farm
