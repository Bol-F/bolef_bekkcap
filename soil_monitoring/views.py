from datetime import timedelta

from django.db import connection
from django.db.models import Avg, Min, Max, Count, OuterRef, Subquery, Q, F
from django.db.models.functions import Extract, Now
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.shortcuts import get_object_or_404

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from farm.models import Field
from .models import FieldSoilProfile, SensorReading, Recommendation, Notification
from .serializers import (
    FieldSoilProfileSerializer,
    SensorReadingSerializer,
    SensorReadingCreateSerializer,
    RecommendationSerializer,
    NotificationSerializer,
    FieldStatisticsSerializer,
    FieldHealthSerializer,
)
from .services import SoilAnalysisService


def _parse_dt(value: str):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    d = parse_date(value)
    if d:
        return timezone.make_aware(timezone.datetime(d.year, d.month, d.day, 0, 0, 0))
    return None


class FieldSoilProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FieldSoilProfileSerializer

    def get_queryset(self):
        return FieldSoilProfile.objects.select_related("field", "field__farm").filter(
            field__farm__owner=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save()


class SensorReadingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SensorReading.objects.select_related(
            "field", "field__farm", "field__soil_profile"
        ).filter(field__farm__owner=self.request.user)

        field_id = self.request.query_params.get("field_id")
        if field_id:
            qs = qs.filter(field_id=field_id)

        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source=source)

        start_dt = _parse_dt(self.request.query_params.get("start_date", ""))
        end_dt = _parse_dt(self.request.query_params.get("end_date", ""))

        if start_dt:
            qs = qs.filter(ts__gte=start_dt)
        if end_dt:
            qs = qs.filter(ts__lte=end_dt)

        qs = qs.order_by("-ts")

        limit = self.request.query_params.get("limit")
        if limit:
            try:
                qs = qs[: int(limit)]
            except (ValueError, TypeError):
                pass

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "bulk_create"):
            return SensorReadingCreateSerializer
        return SensorReadingSerializer

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        readings_data = request.data if isinstance(request.data, list) else [request.data]
        serializer = SensorReadingCreateSerializer(
            data=readings_data,
            many=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        readings = serializer.save()
        return Response(SensorReadingSerializer(readings, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def latest(self, request):
        owner_fields = Field.objects.filter(farm__owner=request.user)

        latest_id_subq = SensorReading.objects.filter(
            field_id=OuterRef("pk")
        ).order_by("-ts").values("id")[:1]

        latest_ids = owner_fields.annotate(
            latest_reading_id=Subquery(latest_id_subq)
        ).values_list("latest_reading_id", flat=True)

        latest_readings = SensorReading.objects.filter(
            id__in=list(latest_ids)
        ).select_related("field").order_by("-ts")

        return Response(SensorReadingSerializer(latest_readings, many=True).data)


class RecommendationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        qs = Recommendation.objects.select_related("field", "field__farm").filter(
            field__farm__owner=self.request.user
        )
        if connection.features.has_native_duration_field:
            qs = qs.annotate(age_hours=Extract(Now() - F("created_at"), "epoch") / 3600.0)

        field_id = self.request.query_params.get("field_id")
        if field_id:
            qs = qs.filter(field_id=field_id)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        severity = self.request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        rec = self.get_object()
        rec.is_active = False
        rec.save(update_fields=["is_active"])
        return Response(self.get_serializer(rec).data)

    @action(detail=False, methods=["post"])
    def deactivate_all(self, request):
        field_id = request.data.get("field_id")
        if not field_id:
            return Response({"detail": "field_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        field = get_object_or_404(Field, id=field_id, farm__owner=request.user)
        updated = Recommendation.objects.filter(field=field, is_active=True).update(is_active=False)
        return Response({"detail": f"Deactivated {updated} recommendations"})


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.select_related(
        "user", "recommendation", "recommendation__field"
    ).all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        channel = self.request.query_params.get("channel")
        if channel:
            qs = qs.filter(channel=channel)

        return qs.order_by("-created_at")


class FieldAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response(
            {"detail": "Use /analytics/statistics/, /analytics/health/, /analytics/dashboard/, /analytics/analyze/"}
        )

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        field_id = request.query_params.get("field_id")
        days = int(request.query_params.get("days", 7))

        if not field_id:
            return Response({"detail": "field_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        field = get_object_or_404(Field, id=field_id, farm__owner=request.user)

        start_date = timezone.now() - timedelta(days=days)
        readings = SensorReading.objects.filter(field=field, ts__gte=start_date)

        if not readings.exists():
            return Response({"detail": "No readings available for this period"}, status=status.HTTP_404_NOT_FOUND)

        stats = readings.aggregate(
            moisture_vwc_avg=Avg("moisture_vwc"),
            moisture_vwc_min=Min("moisture_vwc"),
            moisture_vwc_max=Max("moisture_vwc"),
            ph_avg=Avg("ph"),
            ph_min=Min("ph"),
            ph_max=Max("ph"),
            ec_ds_m_avg=Avg("ec_ds_m"),
            ec_ds_m_min=Min("ec_ds_m"),
            ec_ds_m_max=Max("ec_ds_m"),
            temp_c_avg=Avg("soil_temp_c"),
            temp_c_min=Min("soil_temp_c"),
            temp_c_max=Max("soil_temp_c"),
            readings_count=Count("id"),
        )

        stats["moisture_percent_avg"] = stats["moisture_vwc_avg"] * 100 if stats["moisture_vwc_avg"] is not None else None

        rec_stats = Recommendation.objects.filter(field=field, is_active=True).aggregate(
            active_recommendations=Count("id"),
            critical_recommendations=Count(
                "id", filter=Q(severity=Recommendation.Severity.HIGH)
            ),
        )
        stats.update(rec_stats)

        stats["field_id"] = field.id
        stats["field_name"] = field.name
        stats["period_days"] = days

        return Response(FieldStatisticsSerializer(stats).data)

    @action(detail=False, methods=["get"])
    def health(self, request):
        field_id = request.query_params.get("field_id")
        days = int(request.query_params.get("days", 7))

        if not field_id:
            return Response({"detail": "field_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # ownership enforced:
        get_object_or_404(Field, id=int(field_id), farm__owner=request.user)

        health_data = SoilAnalysisService.calculate_field_health(int(field_id), days)
        if "error" in health_data:
            return Response(health_data, status=status.HTTP_404_NOT_FOUND)

        return Response(FieldHealthSerializer(health_data).data)

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        owner_fields = Field.objects.filter(farm__owner=request.user)

        total_fields = owner_fields.count()
        fields_with_sensors = SensorReading.objects.filter(field__in=owner_fields).values("field").distinct().count()

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        readings_today = SensorReading.objects.filter(field__in=owner_fields, ts__gte=today_start).count()

        active_recs = Recommendation.objects.filter(
            field__in=owner_fields, is_active=True
        )
        summary = active_recs.aggregate(
            total_active_recommendations=Count("id"),
            critical_recommendations=Count(
                "id", filter=Q(severity=Recommendation.Severity.HIGH)
            ),
            fields_need_attention=Count(
                "field", filter=Q(severity=Recommendation.Severity.HIGH), distinct=True
            ),
        )
        rec_by_category = {
            row["category"]: row["count"]
            for row in active_recs.values("category").annotate(count=Count("id"))
        }
        rec_by_severity = {
            row["severity"]: row["count"]
            for row in active_recs.values("severity").annotate(count=Count("id"))
        }
        for c in Recommendation.Category:
            rec_by_category.setdefault(c.value, 0)
        for s in Recommendation.Severity:
            rec_by_severity.setdefault(s.value, 0)

        recent_recommendations = active_recs.select_related("field").order_by("-created_at")
        if connection.features.has_native_duration_field:
            recent_recommendations = recent_recommendations.annotate(
                age_hours=Extract(Now() - F("created_at"), "epoch") / 3600.0
            )
        recent_recommendations = recent_recommendations[:5]

        return Response(
            {
                "total_fields": total_fields,
                "fields_with_sensors": fields_with_sensors,
                "readings_today": readings_today,
                "active_recommendations": summary["total_active_recommendations"],
                "critical_recommendations": summary["critical_recommendations"],
                "fields_need_attention": summary["fields_need_attention"],
                "recommendations_by_category": rec_by_category,
                "recommendations_by_severity": rec_by_severity,
                "recent_recommendations": RecommendationSerializer(recent_recommendations, many=True).data,
                "timestamp": timezone.now(),
            }
        )

    @action(detail=False, methods=["post"])
    def analyze(self, request):
        field_id = request.data.get("field_id")
        if not field_id:
            return Response({"detail": "field_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        field = get_object_or_404(Field, id=int(field_id), farm__owner=request.user)

        latest_reading = SensorReading.objects.filter(field=field).order_by("-ts").first()
        if not latest_reading:
            return Response({"detail": "No readings available for analysis"}, status=status.HTTP_404_NOT_FOUND)

        recommendations = SoilAnalysisService.analyze_reading(latest_reading)

        return Response(
            {
                "detail": f"Analysis complete. Created {len(recommendations)} recommendations.",
                "recommendations": RecommendationSerializer(recommendations, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )
