import logging
from typing import List, Dict, Any, Optional
from datetime import timedelta

from django.utils import timezone
from django.db.models import Avg, Count

from .models import SensorReading, FieldSoilProfile, Recommendation, Notification

logger = logging.getLogger(__name__)


class SoilAnalysisService:
    """Анализ показаний датчиков и генерация рекомендаций + уведомлений владельцу фермы."""

    HEALTH_WEIGHT_MOISTURE = 0.35
    HEALTH_WEIGHT_PH = 0.25
    HEALTH_WEIGHT_EC = 0.25
    HEALTH_WEIGHT_TEMP = 0.15

    @classmethod
    def analyze_reading(cls, reading: SensorReading) -> List[Recommendation]:
        recommendations: List[Recommendation] = []
        reading = (
            SensorReading.objects.select_related(
                "field", "field__farm", "field__soil_profile"
            )
            .filter(pk=reading.pk)
            .first()
            or reading
        )

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
    # analyzers
    # -------------------------
    @classmethod
    def _analyze_moisture(
        cls, reading: SensorReading, profile: FieldSoilProfile
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []
        irrigation_threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (
            1 - profile.mad
        )

        if reading.moisture_vwc < profile.pwp_vwc:
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.IRRIGATION,
                    severity=Recommendation.Severity.HIGH,
                    title="🚨 КРИТИЧЕСКАЯ СУХОСТЬ ПОЧВЫ",
                    message=(
                        f"Влажность почвы ({reading.moisture_vwc * 100:.1f}%) ниже точки "
                        f"постоянного увядания ({profile.pwp_vwc * 100:.1f}%). "
                        f"ТРЕБУЕТСЯ СРОЧНЫЙ ПОЛИВ!"
                    ),
                    evidence={
                        "moisture_vwc": reading.moisture_vwc,
                        "pwp_vwc": profile.pwp_vwc,
                        "fc_vwc": profile.fc_vwc,
                        "threshold": irrigation_threshold,
                        "reading_id": reading.id,
                        "depth_cm": reading.depth_cm,
                    },
                )
            )
        elif reading.moisture_vwc < irrigation_threshold:
            depletion_pct = (
                (profile.fc_vwc - reading.moisture_vwc)
                / (profile.fc_vwc - profile.pwp_vwc)
            ) * 100
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.IRRIGATION,
                    severity=Recommendation.Severity.MED,
                    title="💧 Требуется полив",
                    message=(
                        f"Влажность почвы ({reading.moisture_vwc * 100:.1f}%) ниже порога MAD "
                        f"({irrigation_threshold * 100:.1f}%). "
                        f"Истощение: {depletion_pct:.0f}%. Рекомендуется полив."
                    ),
                    evidence={
                        "moisture_vwc": reading.moisture_vwc,
                        "threshold": irrigation_threshold,
                        "depletion_pct": depletion_pct,
                        "mad": profile.mad,
                        "reading_id": reading.id,
                    },
                )
            )
        elif reading.moisture_vwc > profile.fc_vwc * 1.15:
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.IRRIGATION,
                    severity=Recommendation.Severity.MED,
                    title="⚠️ Переувлажнение почвы",
                    message=(
                        f"Влажность почвы ({reading.moisture_vwc * 100:.1f}%) значительно "
                        f"превышает полевую влагоемкость ({profile.fc_vwc * 100:.1f}%). "
                        f"Проверьте дренаж. Прекратите полив."
                    ),
                    evidence={
                        "moisture_vwc": reading.moisture_vwc,
                        "fc_vwc": profile.fc_vwc,
                        "excess_pct": (reading.moisture_vwc - profile.fc_vwc) * 100,
                        "reading_id": reading.id,
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_ph(
        cls, reading: SensorReading, profile: FieldSoilProfile
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.ph < profile.ph_min:
            deviation = profile.ph_min - reading.ph
            severity = (
                Recommendation.Severity.HIGH
                if deviation > 1.0
                else Recommendation.Severity.MED
            )
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_PH,
                    severity=severity,
                    title="🔬 Почва слишком кислая",
                    message=(
                        f"pH почвы ({reading.ph:.2f}) ниже минимального порога ({profile.ph_min:.2f}). "
                        f"Отклонение: {deviation:.2f}. "
                        f"Рекомендации: Внесите известь (CaCO₃) или доломит для повышения pH."
                    ),
                    evidence={
                        "ph": reading.ph,
                        "ph_min": profile.ph_min,
                        "ph_max": profile.ph_max,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": [
                            "Известкование (CaCO₃)",
                            "Доломитовая мука (CaMg(CO₃)₂)",
                            "Древесная зола",
                        ],
                    },
                )
            )

        elif reading.ph > profile.ph_max:
            deviation = reading.ph - profile.ph_max
            severity = (
                Recommendation.Severity.HIGH
                if deviation > 1.0
                else Recommendation.Severity.MED
            )
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_PH,
                    severity=severity,
                    title="🔬 Почва слишком щелочная",
                    message=(
                        f"pH почвы ({reading.ph:.2f}) выше максимального порога ({profile.ph_max:.2f}). "
                        f"Отклонение: {deviation:.2f}. "
                        f"Рекомендации: Внесите серу или органические кислоты."
                    ),
                    evidence={
                        "ph": reading.ph,
                        "ph_min": profile.ph_min,
                        "ph_max": profile.ph_max,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": [
                            "Элементарная сера",
                            "Сульфат алюминия",
                            "Торф",
                            "Органические мульчи",
                        ],
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_ec(
        cls, reading: SensorReading, profile: FieldSoilProfile
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.ec_ds_m > profile.ec_max_ds_m:
            excess_pct = (
                (reading.ec_ds_m - profile.ec_max_ds_m) / profile.ec_max_ds_m
            ) * 100

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
                        f"EC почвы ({reading.ec_ds_m:.2f} dS/m) превышает порог "
                        f"({profile.ec_max_ds_m:.2f} dS/m) на {excess_pct:.0f}%. "
                        f"Почва {level}. Рекомендации: промывка, дренаж."
                    ),
                    evidence={
                        "ec_ds_m": reading.ec_ds_m,
                        "ec_max_ds_m": profile.ec_max_ds_m,
                        "excess_pct": excess_pct,
                        "salinity_level": level,
                        "reading_id": reading.id,
                        "recommendations": [
                            "Промывка почвы большим объемом воды",
                            "Улучшение дренажа",
                            "Солеустойчивые культуры",
                            "Гипс (CaSO₄) для вытеснения натрия",
                        ],
                    },
                )
            )

        return recommendations

    @classmethod
    def _analyze_temperature(
        cls, reading: SensorReading, profile: FieldSoilProfile
    ) -> List[Recommendation]:
        recommendations: List[Recommendation] = []

        if reading.soil_temp_c < profile.temp_min_c:
            deviation = profile.temp_min_c - reading.soil_temp_c
            severity = (
                Recommendation.Severity.HIGH
                if deviation > 5
                else Recommendation.Severity.LOW
            )
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_TEMP,
                    severity=severity,
                    title="❄️ Низкая температура почвы",
                    message=(
                        f"Температура почвы ({reading.soil_temp_c:.1f}°C) ниже минимума "
                        f"({profile.temp_min_c:.1f}°C). Рост корней замедлен."
                    ),
                    evidence={
                        "soil_temp_c": reading.soil_temp_c,
                        "temp_min_c": profile.temp_min_c,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": [
                            "Мульчирование",
                            "Пленочные укрытия",
                            "Отложить посадку",
                        ],
                    },
                )
            )

        elif reading.soil_temp_c > profile.temp_max_c:
            deviation = reading.soil_temp_c - profile.temp_max_c
            severity = (
                Recommendation.Severity.HIGH
                if deviation > 5
                else Recommendation.Severity.MED
            )
            recommendations.append(
                cls._create_recommendation(
                    field=reading.field,
                    category=Recommendation.Category.SOIL_TEMP,
                    severity=severity,
                    title="🌡️ Высокая температура почвы",
                    message=(
                        f"Температура почвы ({reading.soil_temp_c:.1f}°C) выше максимума "
                        f"({profile.temp_max_c:.1f}°C). Стресс для корней."
                    ),
                    evidence={
                        "soil_temp_c": reading.soil_temp_c,
                        "temp_max_c": profile.temp_max_c,
                        "deviation": deviation,
                        "reading_id": reading.id,
                        "recommendations": ["Мульча", "Чаще полив", "Притенение"],
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

        logger.info(
            "Created recommendation %s/%s for field %s", category, severity, field.id
        )
        return recommendation

    @classmethod
    def _notify_farm_owner(cls, recommendation: Recommendation) -> None:
        """
        Field owner == Farm owner => notify recommendation.field.farm.owner
        """
        try:
            owner = recommendation.field.farm.owner
        except Exception:
            logger.warning(
                "Cannot resolve owner for recommendation %s", recommendation.id
            )
            return

        # IN_APP = notification exists in DB, so we mark it as SENT
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
            },
            sent_at=timezone.now(),
        )

    # -------------------------
    # health calculation
    # -------------------------
    @classmethod
    def calculate_field_health(cls, field_id: int, days: int = 7) -> Dict[str, Any]:
        from farm.models import Field

        field = Field.objects.select_related("soil_profile").get(id=field_id)

        try:
            profile = field.soil_profile
        except FieldSoilProfile.DoesNotExist:
            return {"error": "No soil profile configured for this field"}

        cutoff = timezone.now() - timedelta(days=days)
        readings = SensorReading.objects.filter(field_id=field_id, ts__gte=cutoff)
        latest_reading = readings.select_related(
            "field", "field__farm", "field__soil_profile"
        ).first()
        if latest_reading is None:
            return {"error": "No readings available for this period"}

        stats = readings.aggregate(
            readings_count=Count("id"),
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
            moisture_health["score"] * cls.HEALTH_WEIGHT_MOISTURE
            + ph_health["score"] * cls.HEALTH_WEIGHT_PH
            + ec_health["score"] * cls.HEALTH_WEIGHT_EC
            + temp_health["score"] * cls.HEALTH_WEIGHT_TEMP
        )

        if overall_score >= 80:
            health_status = "excellent"
        elif overall_score >= 60:
            health_status = "good"
        elif overall_score >= 40:
            health_status = "fair"
        else:
            health_status = "poor"

        active_recs = Recommendation.objects.filter(
            field_id=field_id, is_active=True
        ).count()

        threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (
            1 - profile.mad
        )
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
    def _evaluate_moisture_health(
        cls, moisture_vwc: Optional[float], profile: FieldSoilProfile
    ) -> Dict:
        if moisture_vwc is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (
            1 - profile.mad
        )

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
    def _evaluate_ph_health(
        cls, ph: Optional[float], profile: FieldSoilProfile
    ) -> Dict:
        if ph is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if profile.ph_min <= ph <= profile.ph_max:
            return {"score": 100, "status": "optimal", "message": "Оптимально"}
        if ph < profile.ph_min - 1.0 or ph > profile.ph_max + 1.0:
            return {"score": 30, "status": "poor", "message": "Требуется коррекция"}
        return {"score": 60, "status": "fair", "message": "Допустимо"}

    @classmethod
    def _evaluate_ec_health(
        cls, ec: Optional[float], profile: FieldSoilProfile
    ) -> Dict:
        if ec is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if ec <= profile.ec_max_ds_m:
            return {"score": 100, "status": "normal", "message": "Нормально"}
        if ec <= profile.ec_max_ds_m * 1.5:
            return {"score": 60, "status": "elevated", "message": "Повышена"}
        return {"score": 30, "status": "saline", "message": "Засолена"}

    @classmethod
    def _evaluate_temp_health(
        cls, temp: Optional[float], profile: FieldSoilProfile
    ) -> Dict:
        if temp is None:
            return {"score": 0, "status": "unknown", "message": "No data"}

        if profile.temp_min_c <= temp <= profile.temp_max_c:
            return {"score": 100, "status": "optimal", "message": "Оптимально"}
        if temp < profile.temp_min_c - 5 or temp > profile.temp_max_c + 5:
            return {"score": 40, "status": "extreme", "message": "Экстремально"}
        return {"score": 70, "status": "suboptimal", "message": "Допустимо"}
