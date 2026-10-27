from rest_framework import serializers

from .models import Crop, Farm, Planting


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = "__all__"


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = "__all__"


class PlantingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Planting
        fields = "__all__"
