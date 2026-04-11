from rest_framework import viewsets
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
                "yield_record__field",
            )
            .order_by("-sample_date", "-created_at")
        )

    def _validate_ownership_and_relations(self, serializer):
        field = serializer.validated_data.get(
            "field", getattr(serializer.instance, "field", None)
        )
        yield_record = serializer.validated_data.get(
            "yield_record", getattr(serializer.instance, "yield_record", None)
        )

        if not field or field.farm.owner_id != self.request.user.id:
            raise ValidationError({"field": "You do not own this field/farm."})

        if yield_record:
            if yield_record.farm.owner_id != self.request.user.id:
                raise ValidationError(
                    {"yield_record": "You do not own this yield record."}
                )

            if yield_record.farm_id != field.farm_id:
                raise ValidationError(
                    {
                        "yield_record": "Yield record does not belong to the same farm as the selected field."
                    }
                )

            if yield_record.field_id and yield_record.field_id != field.id:
                raise ValidationError(
                    {
                        "yield_record": "Yield record does not belong to the selected field."
                    }
                )

    def perform_create(self, serializer):
        self._validate_ownership_and_relations(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_ownership_and_relations(serializer)
        serializer.save()
