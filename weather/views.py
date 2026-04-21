from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from farm.models import Field
from .models import IrrigationRecommendation, WeatherSnapshot
from .serializers import (
    ErrorResponseSerializer,
    FieldIrrigationPlanResponseSerializer,
    FieldWeatherAdviceResponseSerializer,
    FieldWeatherResponseSerializer,
    IrrigationRecommendationSerializer,
    WeatherHealthResponseSerializer,
    WeatherRefreshRequestSerializer,
    WeatherSnapshotSerializer,
)
from .services import (
    ensure_fresh_irrigation_recommendation,
    ensure_fresh_weather_snapshot,
)


def get_owned_field(user, field_id):
    return get_object_or_404(
        Field.objects.select_related("farm", "farm__owner"),
        pk=field_id,
        farm__owner=user,
    )


class WeatherHealthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="weather_health_check",
        responses={200: WeatherHealthResponseSerializer},
        tags=["Weather"],
    )
    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "weather",
                "provider": "open-meteo",
            }
        )


class FieldForecastView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_weather_forecast",
        request=WeatherRefreshRequestSerializer,
        responses={
            200: FieldWeatherResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["Weather"],
    )
    def post(self, request, field_id):
        field = get_owned_field(request.user, field_id)

        options = WeatherRefreshRequestSerializer(data=request.data or {})
        options.is_valid(raise_exception=True)

        try:
            snapshot = ensure_fresh_weather_snapshot(
                field=field,
                max_age_hours=options.validated_data["max_age_hours"],
                force_refresh=options.validated_data["force_refresh"],
            )
        except ValueError as exc:
            return Response(
                {"error": "Field location is not set", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"error": "Weather forecast failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "snapshot": WeatherSnapshotSerializer(snapshot).data,
            },
            status=status.HTTP_200_OK,
        )


class FieldLatestWeatherView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_weather_latest",
        responses={
            200: FieldWeatherResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=["Weather"],
    )
    def get(self, request, field_id):
        field = get_owned_field(request.user, field_id)

        snapshot = (
            WeatherSnapshot.objects.filter(field=field).order_by("-created_at").first()
        )

        if not snapshot:
            return Response(
                {
                    "error": "No weather snapshot found",
                    "detail": "Call POST /forecast/ first.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "snapshot": WeatherSnapshotSerializer(snapshot).data,
            },
            status=status.HTTP_200_OK,
        )


class FieldIrrigationPlanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_irrigation_plan",
        request=WeatherRefreshRequestSerializer,
        responses={
            200: FieldIrrigationPlanResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["Weather"],
    )
    def post(self, request, field_id):
        field = get_owned_field(request.user, field_id)

        options = WeatherRefreshRequestSerializer(data=request.data or {})
        options.is_valid(raise_exception=True)

        try:
            _, recommendation = ensure_fresh_irrigation_recommendation(
                field=field,
                max_age_hours=options.validated_data["max_age_hours"],
                force_refresh=options.validated_data["force_refresh"],
            )
        except ValueError as exc:
            return Response(
                {"error": "Field location is not set", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"error": "Irrigation plan failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "recommendation": IrrigationRecommendationSerializer(
                    recommendation
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class FieldLatestIrrigationPlanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_irrigation_latest",
        responses={
            200: FieldIrrigationPlanResponseSerializer,
            404: ErrorResponseSerializer,
        },
        tags=["Weather"],
    )
    def get(self, request, field_id):
        field = get_owned_field(request.user, field_id)

        recommendation = (
            IrrigationRecommendation.objects.filter(field=field)
            .select_related("weather_snapshot")
            .order_by("-created_at")
            .first()
        )

        if not recommendation:
            return Response(
                {
                    "error": "No irrigation recommendation found",
                    "detail": "Call POST /irrigation-plan/ first.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "recommendation": IrrigationRecommendationSerializer(
                    recommendation
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class FieldWeatherAdviceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="field_weather_advice",
        request=WeatherRefreshRequestSerializer,
        responses={
            200: FieldWeatherAdviceResponseSerializer,
            400: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
        tags=["Weather"],
    )
    def post(self, request, field_id):
        field = get_owned_field(request.user, field_id)

        options = WeatherRefreshRequestSerializer(data=request.data or {})
        options.is_valid(raise_exception=True)

        try:
            snapshot, recommendation = ensure_fresh_irrigation_recommendation(
                field=field,
                max_age_hours=options.validated_data["max_age_hours"],
                force_refresh=options.validated_data["force_refresh"],
            )
        except ValueError as exc:
            return Response(
                {"error": "Field location is not set", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"error": "Weather advice failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "snapshot": WeatherSnapshotSerializer(snapshot).data,
                "recommendation": IrrigationRecommendationSerializer(
                    recommendation
                ).data,
            },
            status=status.HTTP_200_OK,
        )
