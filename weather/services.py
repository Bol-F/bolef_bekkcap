from __future__ import annotations

from decimal import Decimal
from typing import Any

import requests
from django.utils import timezone

from .models import IrrigationRecommendation, WeatherSnapshot


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_field_coordinates(field) -> tuple[float, float]:
    if field.latitude is not None and field.longitude is not None:
        return float(field.latitude), float(field.longitude)

    polygon = getattr(field, "polygon", None)
    if polygon:
        points = polygon[:-1] if polygon[0] == polygon[-1] else polygon
        lat = sum(p[1] for p in points) / len(points)
        lon = sum(p[0] for p in points) / len(points)
        return float(lat), float(lon)

    raise ValueError("Field has no latitude/longitude or polygon.")


def fetch_open_meteo_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "hourly": (
            "precipitation,"
            "precipitation_probability,"
            "reference_evapotranspiration,"
            "temperature_2m"
        ),
        "forecast_days": days,
        "timezone": "auto",
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def summarize_forecast(data: dict) -> dict:
    hourly = data.get("hourly") or {}

    precipitation = hourly.get("precipitation") or []
    probability = hourly.get("precipitation_probability") or []
    eto = hourly.get("reference_evapotranspiration") or []
    temperature = hourly.get("temperature_2m") or []

    rain_24 = _sum_first(precipitation, 24)
    rain_72 = _sum_first(precipitation, 72)
    eto_24 = _sum_first(eto, 24)
    max_prob_24 = _max_first(probability, 24)
    avg_temp_24 = _avg_first(temperature, 24)

    return {
        "rain_next_24h_mm": round(rain_24, 2),
        "rain_next_72h_mm": round(rain_72, 2),
        "max_rain_probability_24h": round(max_prob_24, 2),
        "evapotranspiration_24h": round(eto_24, 2),
        "avg_temperature_24h": round(avg_temp_24, 2) if avg_temp_24 is not None else None,
        "next_dry_window": find_next_dry_window(hourly),
    }


def find_next_dry_window(hourly: dict, min_hours: int = 6) -> dict | None:
    times = hourly.get("time") or []
    precipitation = hourly.get("precipitation") or []

    if not times or not precipitation:
        return None

    streak = 0
    start_index = None

    for i, rain in enumerate(precipitation):
        rain_value = float(rain or 0)

        if rain_value <= 0.2:
            if streak == 0:
                start_index = i
            streak += 1

            if streak >= min_hours and start_index is not None:
                return {
                    "start_time": times[start_index],
                    "end_time": times[i],
                    "duration_hours": streak,
                }
        else:
            streak = 0
            start_index = None

    return None


def create_weather_snapshot_for_field(field) -> WeatherSnapshot:
    lat, lon = get_field_coordinates(field)
    raw_data = fetch_open_meteo_forecast(lat, lon)
    summary = summarize_forecast(raw_data)

    return WeatherSnapshot.objects.create(
        field=field,
        source="open-meteo",
        latitude=_d(lat),
        longitude=_d(lon),
        forecast_date=timezone.localdate(),
        rain_next_24h_mm=_d(summary["rain_next_24h_mm"]),
        rain_next_72h_mm=_d(summary["rain_next_72h_mm"]),
        max_rain_probability_24h=_d(summary["max_rain_probability_24h"]),
        evapotranspiration_24h=_d(summary["evapotranspiration_24h"]),
        avg_temperature_24h=_d(summary["avg_temperature_24h"]),
        raw_data=raw_data,
    )


def create_irrigation_recommendation_for_field(field) -> IrrigationRecommendation:
    snapshot = create_weather_snapshot_for_field(field)

    soil_context = get_latest_soil_context(field)
    ndvi_context = get_latest_ndvi_context(field)

    decision = build_irrigation_decision(
        weather_snapshot=snapshot,
        soil_context=soil_context,
        ndvi_context=ndvi_context,
    )

    return IrrigationRecommendation.objects.create(
        field=field,
        weather_snapshot=snapshot,
        status=decision["status"],
        severity=decision["severity"],
        recommendation=decision["recommendation"],
        reason=decision["reason"],
        recommended_time=decision["recommended_time"],
        rain_next_24h_mm=snapshot.rain_next_24h_mm,
        rain_next_72h_mm=snapshot.rain_next_72h_mm,
        evapotranspiration_24h=snapshot.evapotranspiration_24h,
        evidence=decision["evidence"],
    )


def build_irrigation_decision(
    weather_snapshot: WeatherSnapshot,
    soil_context: dict[str, Any] | None = None,
    ndvi_context: dict[str, Any] | None = None,
) -> dict:
    rain_24 = float(weather_snapshot.rain_next_24h_mm or 0)
    rain_72 = float(weather_snapshot.rain_next_72h_mm or 0)
    prob_24 = float(weather_snapshot.max_rain_probability_24h or 0)
    eto_24 = float(weather_snapshot.evapotranspiration_24h or 0)

    raw_hourly = (weather_snapshot.raw_data or {}).get("hourly") or {}
    dry_window = find_next_dry_window(raw_hourly)

    soil_moisture = None
    if soil_context:
        soil_moisture = soil_context.get("moisture_percent")

    ndvi_status = None
    if ndvi_context:
        ndvi_status = ndvi_context.get("status")

    evidence = {
        "weather": {
            "rain_next_24h_mm": rain_24,
            "rain_next_72h_mm": rain_72,
            "max_rain_probability_24h": prob_24,
            "evapotranspiration_24h": eto_24,
            "next_dry_window": dry_window,
        },
        "soil": soil_context,
        "ndvi": ndvi_context,
    }

    if soil_moisture is not None and soil_moisture >= 70:
        return {
            "status": "skip_soil_wet",
            "severity": "medium",
            "recommendation": "Do not water now.",
            "reason": (
                f"Soil moisture is already high ({soil_moisture:.1f}%). "
                "Extra irrigation may cause overwatering."
            ),
            "recommended_time": "none",
            "evidence": evidence,
        }

    if rain_72 >= 25:
        return {
            "status": "drainage_warning",
            "severity": "high",
            "recommendation": "Skip irrigation and check drainage after rain.",
            "reason": (
                f"Long or heavy rain is expected in the next 72 hours "
                f"({rain_72:.1f} mm). Risk of overwatering is high."
            ),
            "recommended_time": _dry_window_text(dry_window),
            "evidence": evidence,
        }

    if rain_24 >= 10 or prob_24 >= 75:
        return {
            "status": "skip_rain_expected",
            "severity": "low",
            "recommendation": "Do not water now. Rain is expected.",
            "reason": (
                f"Rain forecast is significant in the next 24 hours "
                f"({rain_24:.1f} mm, probability up to {prob_24:.0f}%)."
            ),
            "recommended_time": _dry_window_text(dry_window),
            "evidence": evidence,
        }

    if soil_moisture is not None and soil_moisture <= 30 and rain_24 < 5:
        return {
            "status": "water_now",
            "severity": "high",
            "recommendation": "Water the crop as soon as possible.",
            "reason": (
                f"Soil moisture is low ({soil_moisture:.1f}%) and little rain is expected "
                f"({rain_24:.1f} mm in 24h)."
            ),
            "recommended_time": "early_morning_or_evening",
            "evidence": evidence,
        }

    if rain_24 < 2 and eto_24 >= 4:
        return {
            "status": "water_now",
            "severity": "medium",
            "recommendation": "Irrigation is recommended.",
            "reason": (
                f"Very low rain is expected ({rain_24:.1f} mm) and evapotranspiration "
                f"is high ({eto_24:.1f})."
            ),
            "recommended_time": "early_morning",
            "evidence": evidence,
        }

    if rain_24 < 5 and eto_24 >= 3:
        return {
            "status": "water_later",
            "severity": "medium",
            "recommendation": "Plan light irrigation later if soil remains dry.",
            "reason": (
                f"Rain is limited ({rain_24:.1f} mm) and evapotranspiration is moderate "
                f"({eto_24:.1f})."
            ),
            "recommended_time": "evening",
            "evidence": evidence,
        }

    if ndvi_status in ("poor", "bare") and rain_24 < 5:
        return {
            "status": "watch",
            "severity": "medium",
            "recommendation": "Monitor the field and check soil moisture before watering.",
            "reason": (
                f"NDVI status is '{ndvi_status}', but weather alone does not prove drought. "
                "Check soil moisture before irrigation."
            ),
            "recommended_time": "after_field_check",
            "evidence": evidence,
        }

    return {
        "status": "watch",
        "severity": "low",
        "recommendation": "No urgent irrigation action is needed.",
        "reason": "Weather conditions do not show clear drought or overwatering risk.",
        "recommended_time": "monitor_next_24h",
        "evidence": evidence,
    }


def get_latest_soil_context(field) -> dict | None:
    try:
        from soil_monitoring.models import SoilMeasurement
    except Exception:
        return None

    measurement = (
        SoilMeasurement.objects.filter(field=field)
        .order_by("-sample_date", "-created_at")
        .first()
    )

    if not measurement:
        return None

    return {
        "measurement_id": measurement.id,
        "sample_date": str(measurement.sample_date),
        "moisture_percent": _float_or_none(measurement.moisture_percent),
        "ph_level": _float_or_none(measurement.ph_level),
        "soil_type": measurement.soil_type,
        "temperature_celsius": _float_or_none(measurement.temperature_celsius),
    }


def get_latest_ndvi_context(field) -> dict | None:
    try:
        from ndvi.models import NDVIRecord
    except Exception:
        return None

    record = NDVIRecord.objects.filter(field=field).order_by("-date").first()

    if not record:
        return None

    return {
        "record_id": record.id,
        "date": str(record.date),
        "ndvi_mean": _float_or_none(record.ndvi_mean),
        "status": record.status,
        "source": record.source,
    }


def _sum_first(values: list, count: int) -> float:
    return sum(float(x or 0) for x in values[:count])


def _max_first(values: list, count: int) -> float:
    sliced = values[:count]
    if not sliced:
        return 0.0
    return max(float(x or 0) for x in sliced)


def _avg_first(values: list, count: int) -> float | None:
    sliced = values[:count]
    if not sliced:
        return None
    return sum(float(x or 0) for x in sliced) / len(sliced)


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _d(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(float(value), 2)))


def _dry_window_text(dry_window: dict | None) -> str:
    if not dry_window:
        return "after_rain_recheck_soil"
    return f"after_rain_from_{dry_window['start_time']}"