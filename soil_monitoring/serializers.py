from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from farm.models import Field, YieldRecord
from .models import SoilMeasurement


class SoilMeasurementSerializer(serializers.ModelSerializer):
    field = serializers.PrimaryKeyRelatedField(queryset=Field.objects.all())
    yield_record = serializers.PrimaryKeyRelatedField(
        queryset=YieldRecord.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SoilMeasurement
        fields = [
            "id",
            "field",
            "yield_record",
            "soil_type",
            "moisture_percent",
            "ph_level",
            "nitrogen",
            "phosphorus",
            "potassium",
            "temperature_celsius",
            "sample_date",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            self.fields["field"].queryset = Field.objects.filter(farm__owner=user)
            self.fields["yield_record"].queryset = YieldRecord.objects.filter(farm__owner=user)

    def validate(self, attrs):
        field = attrs.get("field") or getattr(self.instance, "field", None)
        yield_record = attrs.get("yield_record") or getattr(self.instance, "yield_record", None)

        if yield_record and field and yield_record.field and yield_record.field_id != field.id:
            raise ValidationError(
                {"yield_record": "Yield record does not belong to the selected field."}
            )

        return attrs