from rest_framework import serializers

from .models import IrrigationRecommendation, WeatherSnapshot


class WeatherSnapshotSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)

    class Meta:
        model = WeatherSnapshot
        fields = [
            "id",
            "field",
            "field_name",
            "source",
            "latitude",
            "longitude",
            "forecast_date",
            "rain_next_24h_mm",
            "rain_next_72h_mm",
            "rain_next_7d_mm",
            "max_rain_probability_24h",
            "evapotranspiration_24h",
            "avg_temperature_24h",
            "raw_data",
            "created_at",
        ]
        read_only_fields = fields


class IrrigationRecommendationSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)

    class Meta:
        model = IrrigationRecommendation
        fields = [
            "id",
            "field",
            "field_name",
            "weather_snapshot",
            "status",
            "severity",
            "recommendation",
            "reason",
            "recommended_time",
            "rain_next_24h_mm",
            "rain_next_72h_mm",
            "rain_next_7d_mm",
            "evapotranspiration_24h",
            "evidence",
            "created_at",
        ]
        read_only_fields = fields


class WeatherRefreshRequestSerializer(serializers.Serializer):
    force_refresh = serializers.BooleanField(default=False)
    max_age_hours = serializers.IntegerField(default=18, min_value=1, max_value=48)


class WeatherHealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    provider = serializers.CharField()


class FieldWeatherResponseSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    field_name = serializers.CharField()
    snapshot = WeatherSnapshotSerializer()


class FieldIrrigationPlanResponseSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    field_name = serializers.CharField()
    recommendation = IrrigationRecommendationSerializer()


class FieldWeatherAdviceResponseSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    field_name = serializers.CharField()
    snapshot = WeatherSnapshotSerializer()
    recommendation = IrrigationRecommendationSerializer()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField(required=False, allow_null=True)