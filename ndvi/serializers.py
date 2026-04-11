from datetime import date, timedelta

from rest_framework import serializers

from farm.models import Field
from .models import NDVIRecord


class NDVIRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = NDVIRecord
        fields = [
            "id",
            "date",
            "ndvi_mean",
            "ndvi_min",
            "ndvi_max",
            "ndvi_std",
            "evi_mean",
            "tcg_mean",
            "status",
            "source",
            "cloud_coverage",
        ]


class FieldContextSerializer(serializers.ModelSerializer):
    farm = serializers.IntegerField(source="farm_id", read_only=True)
    polygon = serializers.SerializerMethodField()
    bbox_min_lon = serializers.SerializerMethodField()
    bbox_max_lon = serializers.SerializerMethodField()
    bbox_min_lat = serializers.SerializerMethodField()
    bbox_max_lat = serializers.SerializerMethodField()
    has_location = serializers.SerializerMethodField()
    polygon_area_approx_ha = serializers.SerializerMethodField()

    class Meta:
        model = Field
        fields = [
            "id",
            "farm",
            "name",
            "area",
            "soil_type",
            "latitude",
            "longitude",
            "polygon",
            "bbox_min_lon",
            "bbox_max_lon",
            "bbox_min_lat",
            "bbox_max_lat",
            "has_location",
            "polygon_area_approx_ha",
        ]

    def get_polygon(self, obj):
        return getattr(obj, "polygon", None)

    def get_bbox_min_lon(self, obj):
        return getattr(obj, "bbox_min_lon", None)

    def get_bbox_max_lon(self, obj):
        return getattr(obj, "bbox_max_lon", None)

    def get_bbox_min_lat(self, obj):
        return getattr(obj, "bbox_min_lat", None)

    def get_bbox_max_lat(self, obj):
        return getattr(obj, "bbox_max_lat", None)

    def get_has_location(self, obj):
        has_location_attr = getattr(obj, "has_location", None)
        if has_location_attr is not None:
            return bool(has_location_attr)

        lat = getattr(obj, "latitude", None)
        lon = getattr(obj, "longitude", None)
        polygon = getattr(obj, "polygon", None)
        return bool((lat is not None and lon is not None) or polygon)

    def get_polygon_area_approx_ha(self, obj):
        value = getattr(obj, "polygon_area_approx_ha", None)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class DateRangeSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, data):
        today = date.today()
        data.setdefault("date_from", today - timedelta(days=180))
        data.setdefault("date_to", today)

        if data["date_from"] >= data["date_to"]:
            raise serializers.ValidationError("date_from must be before date_to.")

        if (data["date_to"] - data["date_from"]).days > 730:
            raise serializers.ValidationError("Date range cannot exceed 2 years.")

        return data


class FetchRequestSerializer(DateRangeSerializer):
    force_refresh = serializers.BooleanField(default=False)


class AdHocQuerySerializer(DateRangeSerializer):
    polygon = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(),
            min_length=2,
            max_length=2,
        ),
        min_length=4,
    )

    def validate_polygon(self, value):
        normalized = []
        for pt in value:
            lon, lat = pt
            if not (-180 <= lon <= 180):
                raise serializers.ValidationError(f"Invalid longitude: {lon}")
            if not (-90 <= lat <= 90):
                raise serializers.ValidationError(f"Invalid latitude: {lat}")
            normalized.append([float(lon), float(lat)])

        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])

        return normalized


class NDVIDataPointSerializer(serializers.Serializer):
    date = serializers.CharField()
    ndvi_mean = serializers.FloatField()
    ndvi_min = serializers.FloatField(required=False, allow_null=True)
    ndvi_max = serializers.FloatField(required=False, allow_null=True)
    ndvi_std = serializers.FloatField(required=False, allow_null=True)
    evi_mean = serializers.FloatField(required=False, allow_null=True)
    tcg_mean = serializers.FloatField(required=False, allow_null=True)
    status = serializers.CharField()
    source = serializers.CharField()
    cloud_coverage = serializers.FloatField(required=False, allow_null=True)


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    data_source = serializers.CharField()


class FetchResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    field = FieldContextSerializer()
    new_records = serializers.IntegerField()
    skipped_existing = serializers.IntegerField()
    date_from = serializers.CharField()
    date_to = serializers.CharField()
    source = serializers.CharField()


class TimeSeriesResponseSerializer(serializers.Serializer):
    field = FieldContextSerializer()
    date_from = serializers.CharField()
    date_to = serializers.CharField()
    count = serializers.IntegerField()
    time_series = NDVIDataPointSerializer(many=True)


class AnalysisResponseSerializer(serializers.Serializer):
    field = FieldContextSerializer()
    analysis = serializers.JSONField()


class AdHocQueryResponseSerializer(serializers.Serializer):
    center_lat = serializers.FloatField()
    center_lon = serializers.FloatField()
    count = serializers.IntegerField()
    time_series = NDVIDataPointSerializer(many=True)
    analysis = serializers.JSONField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField(required=False, allow_null=True)
