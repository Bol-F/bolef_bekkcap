import logging
from io import BytesIO

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema

from farm.models import Field
from .models import NDVIRecord, classify_ndvi
from .serializers import (
    AdHocQueryResponseSerializer,
    AdHocQuerySerializer,
    AnalysisResponseSerializer,
    DateRangeSerializer,
    ErrorResponseSerializer,
    FetchRequestSerializer,
    FetchResponseSerializer,
    FieldContextSerializer,
    HealthResponseSerializer,
    NDVIRecordSerializer,
    TimeSeriesResponseSerializer,
)
from .services.analyzer import analyze_trend
from .services.dataset_loader import get_ndvi_data

logger = logging.getLogger(__name__)


def _get_owned_field(user, field_id: int) -> Field:
    return get_object_or_404(
        Field.objects.select_related("farm", "farm__owner"),
        pk=field_id,
        farm__owner=user,
    )


def _field_center(field: Field) -> tuple[float | None, float | None]:
    lat = getattr(field, "latitude", None)
    lon = getattr(field, "longitude", None)

    if lat is not None and lon is not None:
        return float(lat), float(lon)

    polygon = getattr(field, "polygon", None)
    if polygon:
        points = polygon[:-1] if polygon and polygon[0] == polygon[-1] else polygon
        center_lat = sum(p[1] for p in points) / len(points)
        center_lon = sum(p[0] for p in points) / len(points)
        return float(center_lat), float(center_lon)

    return None, None


def _bbox_polygon(lat: float, lon: float, padding: float = 0.01) -> list[list[float]]:
    min_lon = lon - padding
    max_lon = lon + padding
    min_lat = lat - padding
    max_lat = lat + padding

    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def _field_polygon_for_satellite(field: Field) -> list[list[float]] | None:
    polygon = getattr(field, "polygon", None)
    if polygon:
        normalized = [list(p) for p in polygon]
        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])
        return normalized

    lat, lon = _field_center(field)
    if lat is not None and lon is not None:
        return _bbox_polygon(lat, lon)

    return None


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="ndvi_health_check",
        responses=HealthResponseSerializer,
        tags=["NDVI"],
    )
    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "agro-ndvi-backend",
                "data_source": getattr(settings, "NDVI_DATA_SOURCE", "synthetic"),
            }
        )


class FieldNDVIFetchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_ndvi_fetch",
        request=FetchRequestSerializer,
        responses={
            200: FetchResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def post(self, request, field_id):
        field = _get_owned_field(request.user, field_id)

        serializer = FetchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        center_lat, center_lon = _field_center(field)
        polygon = _field_polygon_for_satellite(field)

        if center_lat is None or center_lon is None:
            return Response(
                {
                    "error": "Field location is not set.",
                    "detail": "Set latitude/longitude or polygon on the field first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        d_from = serializer.validated_data["date_from"]
        d_to = serializer.validated_data["date_to"]
        force_refresh = serializer.validated_data["force_refresh"]

        if force_refresh:
            NDVIRecord.objects.filter(
                field=field,
                date__gte=d_from,
                date__lte=d_to,
            ).delete()

        existing_dates = set(
            NDVIRecord.objects.filter(
                field=field,
                date__gte=d_from,
                date__lte=d_to,
            ).values_list("date", flat=True)
        )

        try:
            raw = get_ndvi_data(
                center_lat=center_lat,
                center_lon=center_lon,
                date_from=str(d_from),
                date_to=str(d_to),
                polygon=polygon,
            )
        except Exception as exc:
            logger.exception("NDVI data fetch failed for field %s", field.id)
            return Response(
                {"error": "Data fetch failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        to_create = []
        skipped_existing = 0

        for record in raw:
            record_date = record["date"]

            if record_date in {str(d) for d in existing_dates}:
                skipped_existing += 1
                continue

            to_create.append(
                NDVIRecord(
                    field=field,
                    date=record_date,
                    ndvi_mean=record["ndvi_mean"],
                    ndvi_min=record.get("ndvi_min"),
                    ndvi_max=record.get("ndvi_max"),
                    ndvi_std=record.get("ndvi_std"),
                    evi_mean=record.get("evi_mean"),
                    tcg_mean=record.get("tcg_mean"),
                    cloud_coverage=record.get("cloud_coverage"),
                    status=classify_ndvi(record["ndvi_mean"]),
                    source=record.get(
                        "source", getattr(settings, "NDVI_DATA_SOURCE", "synthetic")
                    ),
                )
            )
            existing_dates.add(record_date)

        created = NDVIRecord.objects.bulk_create(to_create, ignore_conflicts=True)

        return Response(
            {
                "message": f"Fetched {len(created)} new NDVI records for '{field.name}'.",
                "field": FieldContextSerializer(field).data,
                "new_records": len(created),
                "skipped_existing": skipped_existing,
                "date_from": str(d_from),
                "date_to": str(d_to),
                "source": getattr(settings, "NDVI_DATA_SOURCE", "synthetic"),
            }
        )


class FieldTimeSeriesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_ndvi_timeseries",
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: TimeSeriesResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def get(self, request, field_id):
        field = _get_owned_field(request.user, field_id)

        serializer = DateRangeSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d_from = serializer.validated_data["date_from"]
        d_to = serializer.validated_data["date_to"]

        records = NDVIRecord.objects.filter(
            field=field,
            date__gte=d_from,
            date__lte=d_to,
        ).order_by("date")

        return Response(
            {
                "field": FieldContextSerializer(field).data,
                "date_from": str(d_from),
                "date_to": str(d_to),
                "count": records.count(),
                "time_series": NDVIRecordSerializer(records, many=True).data,
            }
        )


class FieldAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_ndvi_analysis",
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name="date_to",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: AnalysisResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def get(self, request, field_id):
        field = _get_owned_field(request.user, field_id)

        serializer = DateRangeSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d_from = serializer.validated_data["date_from"]
        d_to = serializer.validated_data["date_to"]

        records = NDVIRecord.objects.filter(
            field=field,
            date__gte=d_from,
            date__lte=d_to,
        ).order_by("date")

        if not records.exists():
            return Response(
                {"error": "No NDVI records found. Call POST /fetch/ first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        ts = [
            {
                "date": str(r.date),
                "ndvi_mean": r.ndvi_mean,
                "status": r.status,
            }
            for r in records
        ]

        return Response(
            {
                "field": FieldContextSerializer(field).data,
                "analysis": analyze_trend(ts),
            }
        )


class AdHocNDVIQueryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="adhoc_ndvi_query",
        request=AdHocQuerySerializer,
        responses={
            200: AdHocQueryResponseSerializer,
            400: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def post(self, request):
        serializer = AdHocQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        polygon = serializer.validated_data["polygon"]
        points = polygon[:-1] if polygon and polygon[0] == polygon[-1] else polygon

        center_lat = sum(p[1] for p in points) / len(points)
        center_lon = sum(p[0] for p in points) / len(points)

        try:
            ts = get_ndvi_data(
                center_lat=center_lat,
                center_lon=center_lon,
                date_from=str(serializer.validated_data["date_from"]),
                date_to=str(serializer.validated_data["date_to"]),
                polygon=polygon,
            )
        except Exception as exc:
            return Response(
                {"error": "Data fetch failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        analysis = analyze_trend(
            [
                {
                    "date": r["date"],
                    "ndvi_mean": r["ndvi_mean"],
                    "status": r["status"],
                }
                for r in ts
            ]
        )

        return Response(
            {
                "center_lat": round(center_lat, 6),
                "center_lon": round(center_lon, 6),
                "count": len(ts),
                "time_series": ts,
                "analysis": analysis,
            }
        )


class FieldNDVIMapView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_ndvi_map",
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            (200, "image/png"): OpenApiTypes.BINARY,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def get(self, request, field_id):
        field = _get_owned_field(request.user, field_id)
        date = request.query_params.get("date")

        if not date:
            return Response(
                {
                    "error": "Query parameter 'date' is required.",
                    "detail": "Example: ?date=2024-07-01",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if getattr(settings, "NDVI_DATA_SOURCE", "synthetic") != "sentinel_api":
            return Response(
                {
                    "error": "NDVI map endpoint requires sentinel_api mode.",
                    "detail": "Set NDVI_DATA_SOURCE=sentinel_api and configure Sentinel credentials.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        polygon = _field_polygon_for_satellite(field)
        if not polygon:
            return Response(
                {
                    "error": "Field location is not set.",
                    "detail": "Set polygon or latitude/longitude on the field first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from ndvi.services.sentinel import sentinel_service

            png_bytes = sentinel_service.get_ndvi_map_png(
                polygon=polygon,
                date=date,
                width=768,
                height=768,
            )

            buffer = BytesIO(png_bytes)
            buffer.seek(0)

            return FileResponse(
                buffer,
                content_type="image/png",
                filename=f"field_{field.id}_ndvi_{date}.png",
            )
        except Exception as exc:
            return Response(
                {"error": "Failed to generate NDVI map", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class FarmNDVIFetchAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="farm_ndvi_fetch_all",
        request=FetchRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["NDVI"],
    )
    def post(self, request, farm_id):
        serializer = FetchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d_from = serializer.validated_data["date_from"]
        d_to = serializer.validated_data["date_to"]
        force_refresh = serializer.validated_data["force_refresh"]

        fields = Field.objects.filter(
            farm_id=farm_id,
            farm__owner=request.user,
        ).select_related("farm")

        if not fields.exists():
            return Response(
                {"error": "No fields found for this farm."},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = []
        total_new_records = 0
        total_skipped_existing = 0
        failed_fields = 0

        for field in fields:
            center_lat, center_lon = _field_center(field)
            polygon = _field_polygon_for_satellite(field)

            if center_lat is None or center_lon is None:
                results.append(
                    {
                        "field_id": field.id,
                        "field_name": field.name,
                        "status": "skipped",
                        "reason": "Field location is not set.",
                        "new_records": 0,
                        "skipped_existing": 0,
                    }
                )
                continue

            if force_refresh:
                NDVIRecord.objects.filter(
                    field=field,
                    date__gte=d_from,
                    date__lte=d_to,
                ).delete()

            existing_dates = set(
                NDVIRecord.objects.filter(
                    field=field,
                    date__gte=d_from,
                    date__lte=d_to,
                ).values_list("date", flat=True)
            )

            try:
                raw = get_ndvi_data(
                    center_lat=center_lat,
                    center_lon=center_lon,
                    date_from=str(d_from),
                    date_to=str(d_to),
                    polygon=polygon,
                )
            except Exception as exc:
                logger.exception("NDVI bulk fetch failed for field %s", field.id)
                failed_fields += 1
                results.append(
                    {
                        "field_id": field.id,
                        "field_name": field.name,
                        "status": "failed",
                        "reason": str(exc),
                        "new_records": 0,
                        "skipped_existing": 0,
                    }
                )
                continue

            to_create = []
            skipped_existing = 0

            for record in raw:
                record_date = record["date"]

                if record_date in {str(d) for d in existing_dates}:
                    skipped_existing += 1
                    continue

                to_create.append(
                    NDVIRecord(
                        field=field,
                        date=record_date,
                        ndvi_mean=record["ndvi_mean"],
                        ndvi_min=record.get("ndvi_min"),
                        ndvi_max=record.get("ndvi_max"),
                        ndvi_std=record.get("ndvi_std"),
                        evi_mean=record.get("evi_mean"),
                        tcg_mean=record.get("tcg_mean"),
                        cloud_coverage=record.get("cloud_coverage"),
                        status=classify_ndvi(record["ndvi_mean"]),
                        source=record.get(
                            "source",
                            getattr(settings, "NDVI_DATA_SOURCE", "synthetic"),
                        ),
                    )
                )
                existing_dates.add(record_date)

            created = NDVIRecord.objects.bulk_create(to_create, ignore_conflicts=True)

            total_new_records += len(created)
            total_skipped_existing += skipped_existing

            results.append(
                {
                    "field_id": field.id,
                    "field_name": field.name,
                    "status": "ok",
                    "new_records": len(created),
                    "skipped_existing": skipped_existing,
                }
            )

        return Response(
            {
                "farm_id": farm_id,
                "date_from": str(d_from),
                "date_to": str(d_to),
                "fields_processed": len(results),
                "failed_fields": failed_fields,
                "total_new_records": total_new_records,
                "total_skipped_existing": total_skipped_existing,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

