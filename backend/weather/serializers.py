from rest_framework import serializers

from .models import WeatherSnapshot


class WeatherSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherSnapshot
        fields = "__all__"
