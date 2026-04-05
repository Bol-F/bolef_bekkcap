from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from .models import SoilMeasurement
from .serializers import SoilMeasurementSerializer


class SoilMeasurementViewSet(viewsets.ModelViewSet):
    serializer_class = SoilMeasurementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SoilMeasurement.objects.none()

        return (
            SoilMeasurement.objects.filter(field__farm__owner=self.request.user)
            .select_related(
                "field",
                "field__farm",
                "field__farm__owner",
                "yield_record",
                "yield_record__farm",
            )
            .order_by("-sample_date", "-created_at")
        )

    def perform_create(self, serializer):
        field = serializer.validated_data.get("field")
        yield_record = serializer.validated_data.get("yield_record")

        if not field or field.farm.owner != self.request.user:
            raise ValidationError({"field": "You do not own this field/farm."})

        if yield_record:
            if yield_record.farm.owner != self.request.user:
                raise ValidationError(
                    {"yield_record": "You do not own this yield record."}
                )

            if yield_record.field and yield_record.field_id != field.id:
                raise ValidationError(
                    {"yield_record": "Yield record does not belong to the selected field."}
                )

        serializer.save()

    def perform_update(self, serializer):
        field = serializer.validated_data.get("field", serializer.instance.field)
        yield_record = serializer.validated_data.get(
            "yield_record", serializer.instance.yield_record
        )

        if not field or field.farm.owner != self.request.user:
            raise ValidationError({"field": "You do not own this field/farm."})

        if yield_record:
            if yield_record.farm.owner != self.request.user:
                raise ValidationError(
                    {"yield_record": "You do not own this yield record."}
                )

            if yield_record.field and yield_record.field_id != field.id:
                raise ValidationError(
                    {"yield_record": "Yield record does not belong to the selected field."}
                )

        serializer.save()