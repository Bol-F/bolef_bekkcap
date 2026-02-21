from rest_framework import serializers
from django.utils import timezone

from .models import FieldSoilProfile, SensorReading, Recommendation, Notification
from farm.models import Field


def _get_request_user(serializer: serializers.Serializer):
    req = serializer.context.get("request")
    if req and getattr(req, "user", None) and req.user.is_authenticated:
        return req.user
    return None


class FieldSoilProfileSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    irrigation_threshold = serializers.SerializerMethodField()

    class Meta:
        model = FieldSoilProfile
        fields = [
            "id", "field", "field_name",
            "fc_vwc", "pwp_vwc", "mad",
            "ph_min", "ph_max",
            "ec_max_ds_m",
            "temp_min_c", "temp_max_c",
            "irrigation_threshold",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at", "field_name", "irrigation_threshold"]

    def get_irrigation_threshold(self, obj):
        threshold_vwc = obj.pwp_vwc + (obj.fc_vwc - obj.pwp_vwc) * (1 - obj.mad)
        return round(threshold_vwc, 3)

    def validate(self, data):
        # owner check (create/update)
        user = _get_request_user(self)
        field = data.get("field") or getattr(self.instance, "field", None)
        if user and field and field.farm.owner_id != user.id:
            raise serializers.ValidationError("You do not own this field.")

        fc = data.get("fc_vwc", getattr(self.instance, "fc_vwc", None))
        pwp = data.get("pwp_vwc", getattr(self.instance, "pwp_vwc", None))
        if fc is not None and pwp is not None and fc <= pwp:
            raise serializers.ValidationError("Field Capacity должен быть больше Permanent Wilting Point")

        ph_min = data.get("ph_min", getattr(self.instance, "ph_min", None))
        ph_max = data.get("ph_max", getattr(self.instance, "ph_max", None))
        if ph_min is not None and ph_max is not None and ph_min >= ph_max:
            raise serializers.ValidationError("pH min должен быть меньше pH max")

        temp_min = data.get("temp_min_c", getattr(self.instance, "temp_min_c", None))
        temp_max = data.get("temp_max_c", getattr(self.instance, "temp_max_c", None))
        if temp_min is not None and temp_max is not None and temp_min >= temp_max:
            raise serializers.ValidationError("Temp min должна быть меньше Temp max")

        return data


class SensorReadingSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    moisture_percent = serializers.SerializerMethodField()
    ec_us_cm = serializers.SerializerMethodField()
    health_indicators = serializers.SerializerMethodField()

    class Meta:
        model = SensorReading
        fields = [
            "id", "field", "field_name", "ts",
            "moisture_vwc", "moisture_percent",
            "ph", "ec_ds_m", "ec_us_cm",
            "soil_temp_c", "depth_cm",
            "source", "health_indicators",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "field_name", "moisture_percent", "ec_us_cm", "health_indicators"]

    def get_moisture_percent(self, obj):
        return round(obj.moisture_vwc * 100, 1) if obj.moisture_vwc is not None else None

    def get_ec_us_cm(self, obj):
        return round(obj.ec_ds_m * 1000, 0) if obj.ec_ds_m is not None else None

    def get_health_indicators(self, obj):
        indicators = {"moisture_status": None, "ph_status": None, "ec_status": None, "temp_status": None}
        try:
            profile = obj.field.soil_profile
        except FieldSoilProfile.DoesNotExist:
            return indicators

        if obj.moisture_vwc is not None:
            threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)
            if obj.moisture_vwc < profile.pwp_vwc:
                indicators["moisture_status"] = "critical"
            elif obj.moisture_vwc < threshold:
                indicators["moisture_status"] = "low"
            elif obj.moisture_vwc > profile.fc_vwc * 1.15:
                indicators["moisture_status"] = "high"
            else:
                indicators["moisture_status"] = "optimal"

        if obj.ph is not None:
            if obj.ph < profile.ph_min:
                indicators["ph_status"] = "acidic"
            elif obj.ph > profile.ph_max:
                indicators["ph_status"] = "alkaline"
            else:
                indicators["ph_status"] = "optimal"

        if obj.ec_ds_m is not None:
            indicators["ec_status"] = "saline" if obj.ec_ds_m > profile.ec_max_ds_m else "normal"

        if obj.soil_temp_c is not None:
            if obj.soil_temp_c < profile.temp_min_c:
                indicators["temp_status"] = "cold"
            elif obj.soil_temp_c > profile.temp_max_c:
                indicators["temp_status"] = "hot"
            else:
                indicators["temp_status"] = "optimal"

        return indicators


class SensorReadingCreateSerializer(serializers.ModelSerializer):
    field_id = serializers.IntegerField(write_only=True, required=False)
    moisture_percent = serializers.FloatField(write_only=True, required=False)
    ec_us_cm = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = SensorReading
        fields = [
            "field_id", "field", "ts",
            "moisture_vwc", "moisture_percent",
            "ph", "ec_ds_m", "ec_us_cm",
            "soil_temp_c", "depth_cm", "source",
        ]

    def validate(self, data):
        # Convert moisture_percent -> moisture_vwc
        if "moisture_percent" in data and "moisture_vwc" not in data:
            pct = data.pop("moisture_percent")
            if pct is not None and (pct < 0 or pct > 100):
                raise serializers.ValidationError("moisture_percent must be between 0 and 100")
            data["moisture_vwc"] = None if pct is None else pct / 100.0

        # Convert ec_us_cm -> ec_ds_m
        if "ec_us_cm" in data and "ec_ds_m" not in data:
            us = data.pop("ec_us_cm")
            if us is not None and us < 0:
                raise serializers.ValidationError("ec_us_cm must be >= 0")
            data["ec_ds_m"] = None if us is None else us / 1000.0

        # Resolve field
        if "field" not in data and "field_id" not in data:
            raise serializers.ValidationError("field or field_id is required")

        if "field_id" in data and "field" not in data:
            try:
                data["field"] = Field.objects.get(id=data.pop("field_id"))
            except Field.DoesNotExist:
                raise serializers.ValidationError("Field not found")

        # Owner check
        user = _get_request_user(self)
        if user and data.get("field") and data["field"].farm.owner_id != user.id:
            raise serializers.ValidationError("You do not own this field.")

        return data

    def create(self, validated_data):
        reading = SensorReading.objects.create(**validated_data)

        from .services import SoilAnalysisService
        try:
            SoilAnalysisService.analyze_reading(reading)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Analysis failed for reading %s", reading.id)

        return reading


class RecommendationSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    age_hours = serializers.SerializerMethodField()

    class Meta:
        model = Recommendation
        fields = [
            "id", "field", "field_name",
            "category", "severity",
            "title", "message", "evidence",
            "created_at", "is_active", "age_hours",
        ]
        read_only_fields = ["id", "created_at", "field_name", "age_hours"]

    def get_age_hours(self, obj):
        delta = timezone.now() - obj.created_at
        return round(delta.total_seconds() / 3600, 1)


class NotificationSerializer(serializers.ModelSerializer):
    recommendation_title = serializers.CharField(source="recommendation.title", read_only=True)
    recommendation_message = serializers.CharField(source="recommendation.message", read_only=True)
    recommendation_severity = serializers.CharField(source="recommendation.severity", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "user", "recommendation",
            "recommendation_title", "recommendation_message", "recommendation_severity",
            "channel", "status", "payload", "error",
            "created_at", "sent_at",
        ]
        read_only_fields = [
            "id", "created_at", "sent_at",
            "recommendation_title", "recommendation_message", "recommendation_severity",
        ]


class FieldStatisticsSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    field_name = serializers.CharField()
    period_days = serializers.IntegerField()

    moisture_vwc_avg = serializers.FloatField(allow_null=True)
    moisture_vwc_min = serializers.FloatField(allow_null=True)
    moisture_vwc_max = serializers.FloatField(allow_null=True)
    moisture_percent_avg = serializers.FloatField(allow_null=True)

    ph_avg = serializers.FloatField(allow_null=True)
    ph_min = serializers.FloatField(allow_null=True)
    ph_max = serializers.FloatField(allow_null=True)

    ec_ds_m_avg = serializers.FloatField(allow_null=True)
    ec_ds_m_min = serializers.FloatField(allow_null=True)
    ec_ds_m_max = serializers.FloatField(allow_null=True)

    temp_c_avg = serializers.FloatField(allow_null=True)
    temp_c_min = serializers.FloatField(allow_null=True)
    temp_c_max = serializers.FloatField(allow_null=True)

    readings_count = serializers.IntegerField()
    active_recommendations = serializers.IntegerField()
    critical_recommendations = serializers.IntegerField()


class FieldHealthSerializer(serializers.Serializer):
    field_id = serializers.IntegerField()
    field_name = serializers.CharField()

    overall_health_score = serializers.FloatField()
    health_status = serializers.CharField()

    moisture_health = serializers.DictField()
    ph_health = serializers.DictField()
    ec_health = serializers.DictField()
    temp_health = serializers.DictField()

    needs_irrigation = serializers.BooleanField()
    needs_attention = serializers.BooleanField()

    latest_reading = SensorReadingSerializer()
    active_recommendations_count = serializers.IntegerField()