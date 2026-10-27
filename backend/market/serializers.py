from rest_framework import serializers
from decimal import Decimal

from accounts.models import User
from .models import Buyer, MarketPrice, SellListing, TrainingEvent


class MarketPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketPrice
        fields = "__all__"


class BuyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buyer
        fields = "__all__"
        read_only_fields = ("verified", "is_sample_data")


class TrainingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingEvent
        fields = "__all__"
        read_only_fields = ("is_sample_data",)


class SellListingSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source="farmer.user.first_name", read_only=True)
    ward = serializers.CharField(source="farmer.ward.name", read_only=True)
    crop_name = serializers.CharField(source="crop.name", read_only=True)

    class Meta:
        model = SellListing
        fields = (
            "id",
            "farmer",
            "farmer_name",
            "ward",
            "crop",
            "crop_name",
            "quantity_kg",
            "harvest_date",
            "asking_price_per_kg",
            "status",
            "is_sample_data",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "farmer",
            "status",
            "is_sample_data",
            "created_at",
            "updated_at",
        )

    def validate_harvest_date(self, value):
        from django.utils import timezone

        if value < timezone.localdate():
            raise serializers.ValidationError("Harvest date cannot be in the past.")
        return value

    def validate_status(self, value):
        request = self.context.get("request")
        if (
            self.instance
            and request
            and request.user.role == User.Role.FARMER
            and value != self.instance.status
        ):
            raise serializers.ValidationError("Only officers or admins can change listing status.")
        return value

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if request.user.role == User.Role.FARMER:
                fields["status"].read_only = True
        return fields


class PriceCompareQuerySerializer(serializers.Serializer):
    farm_id = serializers.IntegerField(min_value=1)
    crop_id = serializers.IntegerField(min_value=1)
    middleman_price_per_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    quantity_kg = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        default=Decimal("1"),
    )


class PriceLookupQuerySerializer(serializers.Serializer):
    crop = serializers.CharField(max_length=120)
    ward = serializers.CharField(max_length=120)
    language = serializers.ChoiceField(
        choices=("en", "sw", "guz"), required=False, default="en"
    )


class PriceTrendQuerySerializer(serializers.Serializer):
    crop_id = serializers.IntegerField(min_value=1)
    ward_id = serializers.IntegerField(min_value=1, required=False)
    market_name = serializers.CharField(max_length=160, required=False)
