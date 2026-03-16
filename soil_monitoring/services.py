import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Avg

from .models import SensorReading, FieldSoilProfile, Recommendation, Notification

logger = logging.getLogger(__name__)


class SoilAnalysisService:
    """
    Анализ показаний датчиков и генерация рекомендаций + IN_APP уведомлений владельцу фермы.
    Теперь учитывает прогноз дождя (Open-Meteo через weather.services).
    """

    # Порог “дождь скоро” (можешь менять)
    RAIN_MM_NEXT_HOURS = 3.0       # мм осадков за окно
    RAIN_PROB_MAX = 70.0           # макс вероятность осадков (%)
    RAIN_WINDOW_HOURS = 12         # окно прогнозирования

    @classmethod
    def analyze_reading(cls, reading: SensorReading) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        try:
            profile = reading.field.soil_profile
        except FieldSoilProfile.DoesNotExist:
            logger.warning("No soil profile for field %s", reading.field_id)
            return recommendations

        if reading.moisture_vwc is not None:
            recommendations.extend(cls._analyze_moisture(reading, profile))

        if reading.ph is not None:
            recommendations.extend(cls._analyze_ph(reading, profile))

        if reading.ec_ds_m is not None:
            recommendations.extend(cls._analyze_ec(reading, profile))

        if reading.soil_temp_c is not None:
            recommendations.extend(cls._analyze_temperature(reading, profile))

        return recommendations

    # -------------------------
    # WEATHER helpers
    # -------------------------
    @classmethod
    def _get_weather_context(cls, field) -> Optional[Dict[str, Any]]:
        """
        Returns weather context for next RAIN_WINDOW_HOURS hours:
        {
          "will_rain_soon": bool,
          "rain_mm": float,
          "max_prob": float,
          "window_hours": int,
          "source": "open-meteo"
        }
        or None if no coords / provider error.
        """
        if getattr(field, "latitude", None) is None or getattr(field, "longitude", None) is None:
            return None

        try:
            # import inside to avoid hard dependency at import time
            from weather.services import fetch_open_meteo_forecast
        except Exception:
            logger.warning("weather app not available or import failed")
            return None

        lat = float(field.latitude)
        lon = float(field.longitude)

        try:
            data, _from_cache = fetch_open_meteo_forecast(lat=lat, lon=lon, days=2, timezone="auto")
        except Exception as e:
            logger.warning("Weather fetch failed: %s", e)
            return None

        hourly = (data or {}).get("hourly") or {}
        times = hourly.get("time") or []
        precipitation = hourly.get("precipitation") or []
        prob = hourly.get("precipitation_probability") or []

        if not times or not precipitation:
            return None

        now = timezone.now()
        end = now + timedelta(hours=cls.RAIN_WINDOW_HOURS)

        rain_sum = 0.0
        max_prob = 0.0

        # safe iteration by index length
        n = min(len(times), len(precipitation), len(prob) if prob else len(times))
        for i in range(n):
            dt = parse_datetime(times[i])
            if not dt:
                continue
            # dt может быть naive или aware — приводим к aware, если надо
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)

            if dt < now or dt > end:
                continue

            try:
                rain_sum += float(precipitation[i] or 0.0)
            except Exception:
                pass

            if prob:
                try:
                    max_prob = max(max_prob, float(prob[i] or 0.0))
                except Exception:
                    pass

        will_rain_soon = (rain_sum >= cls.RAIN_MM_NEXT_HOURS) or (max_prob >= cls.RAIN_PROB_MAX)

        return {
            "will_rain_soon": bool(will_rain_soon),
            "rain_mm": round(rain_sum, 2),
            "max_prob": round(max_prob, 1),
            "window_hours": cls.RAIN_WINDOW_HOURS,
            "source": "open-meteo",
        }

    # -------------------------
    # analyzers
    # -------------------------
    @classmethod
    def _analyze_moisture(cls, reading: SensorReading, profile: FieldSoilProfile) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        irrigation_threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)
        weather_ctx = cls._get_weather_context(reading.field)

        # 1) CRITICAL dry: ignore weather
        if reading.moisture_vwc < profile.pwp_vwc:
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.IRRIGATION,
                    severity=Recommendation.Severity.HIGH,
                    title="🚨 КРИТИЧЕСКАЯ СУХОСТЬ ПОЧВЫ",
                    message=(
                        f"Влажность ({reading.moisture_vwc * 100:.1f}%) ниже точки увядания "
                        f"({profile.pwp_vwc * 100:.1f}%). ТРЕБУЕТСЯ СРОЧНЫЙ ПОЛИВ!"
                    ),
                    evidence={
                        "moisture_vwc": reading.moisture_vwc,
                        "pwp_vwc": profile.pwp_vwc,
                        "fc_vwc": profile.fc_vwc,
                        "threshold": irrigation_threshold,
                        "reading_id": reading.id,
                        "depth_cm": reading.depth_cm,
                        "weather": weather_ctx,
                    },
                )
            )
            return recommendations

        # 2) Need watering (below MAD threshold) — but check rain soon
        if reading.moisture_vwc < irrigation_threshold:
            depletion_pct = ((profile.fc_vwc - reading.moisture_vwc) / (profile.fc_vwc - profile.pwp_vwc)) * 100

            if weather_ctx and weather_ctx.get("will_rain_soon"):
                # downgrade / suggest delay
                recommendations.append(
                    cls._create_recommendation(
                        field=reading.field,
                        category=Recommendation.Category.IRRIGATION,
                        severity=Recommendation.Severity.LOW,
                        title="🌧️ Полив можно отложить (ожидается дождь)",
                        message=(
                            f"Влажность ({reading.moisture_vwc * 100:.1f}%) ниже порога "
                            f"({irrigation_threshold * 100:.1f}%), истощение: {depletion_pct:.0f}%. "
                            f"Но в ближайшие {weather_ctx['window_hours']}ч прогнозируется дождь "
                            f"(≈{weather_ctx['rain_mm']} мм, max prob {weather_ctx['max_prob']}%). "
                            f"Рекомендуется подождать и переснять показания позже."
                        ),
                        evidence={
                            "moisture_vwc": reading.moisture_vwc,
                            "threshold": irrigation_threshold,
                            "depletion_pct": depletion_pct,
                            "mad": profile.mad,
                            "reading_id": reading.id,
                            "weather": weather_ctx,
                        },
                    )
                )
            else:
                # normal watering recommendation
                recommendations.append(
                    cls._create_recommendation(
                        field=reading.field,
                        category=Recommendation.Category.IRRIGATION,
                        severity=Recommendation.Severity.MED,
                        title="💧 Требуется полив",
                        message=(
                            f"Влажность ({reading.moisture_vwc * 100:.1f}%) ниже порога MAD "
                            f"({irrigation_threshold * 100:.1f}%). Истощение: {depletion_pct:.0f}%. "
                            f"Рекомендуется полив."
                        ),
                        evidence={
                            "moisture_vwc": reading.moisture_vwc,
                            "threshold": irrigation_threshold,
                            "depletion_pct": depletion_pct,
                            "mad": profile.mad,
                            "reading_id": reading.id,
                            "weather": weather_ctx,
                        },
                    )
                )

            return recommendations

        # 3) Overmoist: if rain soon -> stronger warning
        if reading.moisture_vwc > profile.fc_vwc * 1.15:
            severity = Recommendation.Severity.MED
            extra = ""
            if weather_ctx and weather_ctx.get("will_rain_soon"):
                severity = Recommendation.Severity.HIGH
                extra = (
                    f" Дополнительно: ожидается дождь в ближайшие {weather_ctx['window_hours']}ч "
                    f"(≈{weather_ctx['rain_mm']} мм)."
                )

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.IRRIGATION,
                    severity=severity,
                    title="⚠️ Переувлажнение почвы",
                    message=(
                        f"Влажность ({reading.moisture_vwc * 100:.1f}%) значительно выше "
                        f"полевой влагоемкости ({profile.fc_vwc * 100:.1f}%). "
                        f"Проверьте дренаж. Прекратите полив.{extra}"
                    ),
                    evidence={
                        "moisture_vwc": reading.moisture_vwc,
                        "fc_vwc": profile.fc_vwc,
                        "excess_pct": (reading.moisture_vwc - profile.fc_vwc) * 100,
                        "reading_id": reading.id,
                        "weather": weather_ctx,
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_ph(cls, reading: SensorReading, profile: FieldSoilProfile) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.ph < profile.ph_min:
            deviation = profile.ph_min - reading.ph
            severity = Recommendation.Severity.HIGH if deviation > 1.0 else Recommendation.Severity.MED

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_PH,
                    severity=severity,
                    title="🔬 Почва слишком кислая",
                    message=(
                        f"pH ({reading.ph:.2f}) ниже минимума ({profile.ph_min:.2f}). "
                        f"Отклонение: {deviation:.2f}. Рекомендации: известкование/доломит."
                    ),
                    evidence={
                        "ph": reading.ph,
                        "ph_min": profile.ph_min,
                        "ph_max": profile.ph_max,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": ["CaCO₃", "CaMg(CO₃)₂", "Древесная зола"],
                    },
                )
            )

        elif reading.ph > profile.ph_max:
            deviation = reading.ph - profile.ph_max
            severity = Recommendation.Severity.HIGH if deviation > 1.0 else Recommendation.Severity.MED

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_PH,
                    severity=severity,
                    title="🔬 Почва слишком щелочная",
                    message=(
                        f"pH ({reading.ph:.2f}) выше максимума ({profile.ph_max:.2f}). "
                        f"Отклонение: {deviation:.2f}. Рекомендации: сера/кислые органические."
                    ),
                    evidence={
                        "ph": reading.ph,
                        "ph_min": profile.ph_min,
                        "ph_max": profile.ph_max,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": ["Элементарная сера", "Торф", "Органические мульчи"],
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_ec(cls, reading: SensorReading, profile: FieldSoilProfile) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.ec_ds_m > profile.ec_max_ds_m:
            excess_pct = ((reading.ec_ds_m - profile.ec_max_ds_m) / profile.ec_max_ds_m) * 100

            if reading.ec_ds_m > profile.ec_max_ds_m * 2:
                severity = Recommendation.Severity.HIGH
                level = "сильно засолена"
            elif reading.ec_ds_m > profile.ec_max_ds_m * 1.5:
                severity = Recommendation.Severity.HIGH
                level = "умеренно засолена"
            else:
                severity = Recommendation.Severity.MED
                level = "слабо засолена"

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_EC,
                    severity=severity,
                    title="⚡ Повышенная засоленность почвы",
                    message=(
                        f"EC ({reading.ec_ds_m:.2f} dS/m) выше порога ({profile.ec_max_ds_m:.2f}) на {excess_pct:.0f}%. "
                        f"Почва {level}. Рекомендации: промывка, дренаж."
                    ),
                    evidence={
                        "ec_ds_m": reading.ec_ds_m,
                        "ec_max_ds_m": profile.ec_max_ds_m,
                        "excess_pct": excess_pct,
                        "salinity_level": level,
                        "reading_id": reading.id,
                        "recommendations": ["Промывка", "Дренаж", "Солеустойчивые культуры", "Гипс (CaSO₄)"],
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_temperature(cls, reading: SensorReading, profile: FieldSoilProfile) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.soil_temp_c < profile.temp_min_c:
            deviation = profile.temp_min_c - reading.soil_temp_c
            severity = Recommendation.Severity.HIGH if deviation > 5 else Recommendation.Severity.LOW

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_TEMP,
                    severity=severity,
                    title="❄️ Низкая температура почвы",
                    message=(
                        f"Температура ({reading.soil_temp_c:.1f}°C) ниже минимума ({profile.temp_min_c:.1f}°C). "
                        f"Рекомендуется мульчирование/укрытие."
                    ),
                    evidence={
                        "soil_temp_c": reading.soil_temp_c,
                        "temp_min_c": profile.temp_min_c,
                        "deviation": deviation,
                        "reading_id": reading.id,
                    },
                )
            )

        elif reading.soil_temp_c > profile.temp_max_c:
            deviation = reading.soil_temp_c - profile.temp_max_c
            severity = Recommendation.Severity.HIGH if deviation > 5 else Recommendation.Severity.MED

            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_TEMP,
                    severity=severity,
                    title="🌡️ Высокая температура почвы",
                    message=(
                        f"Температура ({reading.soil_temp_c:.1f}°C) выше максимума ({profile.temp_max_c:.1f}°C). "
                        f"Стресс для корней. Мульча/притенение."
                    ),
                    evidence={
                        "soil_temp_c": reading.soil_temp_c,
                        "temp_max_c": profile.temp_max_c,
                        "deviation": deviation,
                        "reading_id": reading.id,
                    },
                )
            )

        return recommendations

    # -------------------------
    # create rec + notification
    # -------------------------
    @classmethod
    def _create_recommendation(
        cls,
        field,
        category: str,
        severity: str,
        title: str,
        message: str,
        evidence: Dict[str, Any],
    ) -> Recommendation:
        cutoff = timezone.now() - timedelta(hours=24)

        Recommendation.objects.filter(
            field=field,
            category=category,
            is_active=True,
            created_at__gte=cutoff,
        ).update(is_active=False)

        recommendation = Recommendation.objects.create(
            field=field,
            category=category,
            severity=severity,
            title=title,
            message=message,
            evidence=evidence,
            is_active=True,
        )

        cls._notify_farm_owner(recommendation)

        logger.info("Created recommendation %s/%s for field %s", category, severity, field.id)
        return recommendation

    @classmethod
    def _notify_farm_owner(cls, recommendation: Recommendation) -> None:
        try:
            owner = recommendation.field.farm.owner
        except Exception:
            logger.warning("Cannot resolve owner for recommendation %s", recommendation.id)
            return

        Notification.objects.create(
            user=owner,
            recommendation=recommendation,
            channel=Notification.Channel.IN_APP,
            status=Notification.Status.SENT,
            payload={
                "field_id": recommendation.field_id,
                "farm_id": recommendation.field.farm_id,
                "category": recommendation.category,
                "severity": recommendation.severity,
                "title": recommendation.title,
                "weather": recommendation.evidence.get("weather"),
            },
            sent_at=timezone.now(),
        )

    # -------------------------
    # health calculation (без погоды)
    # -------------------------
    @classmethod
    def calculate_field_health(cls, field_id: int, days: int = 7) -> Dict[str, Any]:
        from farm.models import Field

        field = Field.objects.get(id=field_id)

        try:
            profile = field.soil_profile
        except FieldSoilProfile.DoesNotExist:
            return {"error": "No soil profile configured for this field"}

        cutoff = timezone.now() - timedelta(days=days)
        readings = SensorReading.objects.filter(field_id=field_id, ts__gte=cutoff)

        if not readings.exists():
            return {"error": "No readings available for this period"}

        latest_reading = readings.order_by("-ts").first()

        stats = readings.aggregate(
            moisture_avg=Avg("moisture_vwc"),
            ph_avg=Avg("ph"),
            ec_avg=Avg("ec_ds_m"),
            temp_avg=Avg("soil_temp_c"),
        )

        moisture_health = cls._evaluate_moisture_health(stats["moisture_avg"], profile)
        ph_health = cls._evaluate_ph_health(stats["ph_avg"], profile)
        ec_health = cls._evaluate_ec_health(stats["ec_avg"], profile)
        temp_health = cls._evaluate_temp_health(stats["temp_avg"], profile)

        overall_score = (
            moisture_health["score"] * 0.35
            + ph_health["score"] * 0.25
            + ec_health["score"] * 0.25
            + temp_health["score"] * 0.15
        )

        if overall_score >= 80:
            health_status = "excellent"
        elif overall_score >= 60:
            health_status = "good"
        elif overall_score >= 40:
            health_status = "fair"
        else:
            health_status = "poor"

        active_recs = Recommendation.objects.filter(field_id=field_id, is_active=True).count()

        threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)
        needs_irrigation = (
            latest_reading is not None
            and latest_reading.moisture_vwc is not None
            and latest_reading.moisture_vwc < threshold
        )

        return {
            "field_id": field_id,
            "field_name": field.name,
            "overall_health_score": round(overall_score, 1),
            "health_status": health_status,
            "moisture_health": moisture_health,
            "ph_health": ph_health,
            "ec_health": ec_health,
            "temp_health": temp_health,
            "needs_irrigation": needs_irrigation,
            "needs_attention": overall_score < 60 or active_recs > 0,
            "active_recommendations_count": active_recs,
            "latest_reading": latest_reading,
        }

    @classmethod
    def _evaluate_moisture_health(cls, moisture_vwc: Optional[float], profile: FieldSoilProfile) -> Dict:
        if moisture_vwc is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)

        if moisture_vwc < profile.pwp_vwc:
            return {"score": 10, "status": "critical", "message": "Критическая сухость"}
        if moisture_vwc < threshold:
            return {"score": 50, "status": "low", "message": "Нужен полив"}
        if moisture_vwc > profile.fc_vwc * 1.15:
            return {"score": 60, "status": "high", "message": "Переувлажнение"}
        if threshold <= moisture_vwc <= profile.fc_vwc:
            return {"score": 100, "status": "optimal", "message": "Оптимально"}
        return {"score": 80, "status": "good", "message": "Хорошо"}

    @classmethod
    def _evaluate_ph_health(cls, ph: Optional[float], profile: FieldSoilProfile) -> Dict:
        if ph is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if profile.ph_min <= ph <= profile.ph_max:
            return {"score": 100, "status": "optimal", "message": "Оптимально"}
        if ph < profile.ph_min - 1.0 or ph > profile.ph_max + 1.0:
            return {"score": 30, "status": "poor", "message": "Требуется коррекция"}
        return {"score": 60, "status": "fair", "message": "Допустимо"}

    @classmethod
    def _evaluate_ec_health(cls, ec: Optional[float], profile: FieldSoilProfile) -> Dict:
        if ec is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if ec <= profile.ec_max_ds_m:
            return {"score": 100, "status": "normal", "message": "Нормально"}
        if ec <= profile.ec_max_ds_m * 1.5:
            return {"score": 60, "status": "elevated", "message": "Повышена"}
        return {"score": 30, "status": "saline", "message": "Засолена"}

    @classmethod
    def _evaluate_temp_health(cls, temp: Optional[float], profile: FieldSoilProfile) -> Dict:
        if temp is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if profile.temp_min_c <= temp <= profile.temp_max_c:
            return {"score": 100, "status": "optimal", "message": "Оптимально"}
        if temp < profile.temp_min_c - 5 or temp > profile.temp_max_c + 5:
            return {"score": 40, "status": "extreme", "message": "Экстремально"}
        return {"score": 70, "status": "suboptimal", "message": "Допустимо"}