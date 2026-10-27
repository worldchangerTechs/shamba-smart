from rest_framework import serializers

from .models import AdviceContent, AdviceRecommendation


class AdviceContentSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()

    class Meta:
        model = AdviceContent
        fields = (
            "code",
            "service",
            "title",
            "body",
            "title_en",
            "title_sw",
            "title_guz",
            "body_en",
            "body_sw",
            "body_guz",
            "cost_min_kes_per_acre",
            "cost_max_kes_per_acre",
            "effort",
            "metadata",
        )

    def _localized(self, obj, field):
        language = self.context["request"].user.language
        return getattr(obj, f"{field}_{language}") or getattr(obj, f"{field}_en")

    def get_title(self, obj) -> str:
        return self._localized(obj, "title")

    def get_body(self, obj) -> str:
        return self._localized(obj, "body")


class UdongoDoctorInputSerializer(serializers.Serializer):
    crop = serializers.CharField(max_length=120)
    farm_id = serializers.IntegerField(required=False, min_value=1)
    soil_ph = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=14)
    quiz = serializers.DictField(required=False)

    def validate(self, attrs):
        has_ph = "soil_ph" in attrs and attrs["soil_ph"] is not None
        has_quiz = "quiz" in attrs
        if has_ph == has_quiz:
            raise serializers.ValidationError(
                "Provide either soil_ph or all six visual quiz answers."
            )
        if has_quiz:
            answers = attrs["quiz"]
            expected = {
                "leaf_colour",
                "soil_colour",
                "past_yields",
                "rain_washing",
                "mulch_use",
                "manure_use",
            }
            if set(answers) != expected:
                raise serializers.ValidationError(
                    {"quiz": f"Provide exactly these answers: {', '.join(sorted(expected))}."}
                )
            choices = {
                "leaf_colour": {"pale", "yellow", "green"},
                "soil_colour": {"pale", "dark"},
                "past_yields": {"falling", "steady", "good"},
                "rain_washing": {"yes", "no"},
                "mulch_use": {"yes", "no"},
                "manure_use": {"yes", "no"},
            }
            for field, allowed in choices.items():
                value = answers[field]
                if not isinstance(value, str) or value.casefold() not in allowed:
                    raise serializers.ValidationError(
                        {"quiz": {field: f"Choose one of: {', '.join(sorted(allowed))}."}}
                    )
                answers[field] = value.casefold()
        return attrs


class MteremkoGuardInputSerializer(serializers.Serializer):
    farm_id = serializers.IntegerField(min_value=1)
    ground_cover_percent = serializers.IntegerField(min_value=0, max_value=100)
    tillage = serializers.ChoiceField(choices=("upslope", "conventional", "contour"))


class PpeGapInputSerializer(serializers.Serializer):
    farm_id = serializers.IntegerField(required=False, min_value=1)
    owned_items = serializers.ListField(
        child=serializers.ChoiceField(
            choices=("mask", "gloves", "boots", "overall", "goggles")
        ),
        allow_empty=True,
    )


class TakaLoopInputSerializer(serializers.Serializer):
    waste_type = serializers.ChoiceField(
        choices=("CROP_RESIDUE", "CHEMICAL_CONTAINER", "PACKAGING")
    )
    farm_id = serializers.IntegerField(required=False, min_value=1)


class AdviceRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdviceRecommendation
        fields = "__all__"
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        farmer = attrs.get("farmer", getattr(self.instance, "farmer", None))
        farm = attrs.get("farm", getattr(self.instance, "farm", None))
        if farm and farmer and farm.farmer_id != farmer.pk:
            raise serializers.ValidationError({"farm": "The farm must belong to the selected farmer."})
        return attrs
