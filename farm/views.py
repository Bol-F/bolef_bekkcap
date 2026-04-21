from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .irrigation_service import calculate_watering_status, get_field_weather_forecast
from .ml_service import predict_yield_for_record
from .models import (
    ActivityLog,
    Animal,
    Crop,
    EmailOTP,
    Farm,
    Field,
    UserProfile,
    YieldRecord,
)
from .serializers import (
    ActivityLogSerializer,
    AnimalSerializer,
    CropSerializer,
    FarmSerializer,
    FieldSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    YieldRecordSerializer,
)

User = get_user_model()


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _otp_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_password_reset_email(email: str, code: str):
    subject = "Your password reset code"
    message = (
        f"Your password reset code is: {code}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"If you did not request this, you can ignore this email."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[email],
        fail_silently=False,
    )


class BaseOwnedModelViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        raise NotImplementedError


class FarmViewSet(BaseOwnedModelViewSet):
    serializer_class = FarmSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Farm.objects.none()

        return Farm.objects.filter(owner=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldViewSet(BaseOwnedModelViewSet):
    serializer_class = FieldSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Field.objects.none()

        return (
            Field.objects.filter(farm__owner=self.request.user)
            .select_related("farm", "farm__owner")
            .order_by("farm_id", "name")
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class CropViewSet(BaseOwnedModelViewSet):
    serializer_class = CropSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Crop.objects.none()

        return (
            Crop.objects.filter(field__farm__owner=self.request.user)
            .select_related("field", "field__farm", "field__farm__owner")
            .order_by("-id")
        )

    def perform_create(self, serializer):
        field = serializer.validated_data.get("field")
        if not field or field.farm.owner_id != self.request.user.id:
            raise ValidationError({"field": "You do not own this field."})
        serializer.save()

    def perform_update(self, serializer):
        field = serializer.validated_data.get("field", serializer.instance.field)
        if not field or field.farm.owner_id != self.request.user.id:
            raise ValidationError({"field": "You do not own this field."})
        serializer.save()


class AnimalViewSet(BaseOwnedModelViewSet):
    serializer_class = AnimalSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Animal.objects.none()

        return (
            Animal.objects.filter(farm__owner=self.request.user)
            .select_related("farm", "farm__owner")
            .order_by("species", "tag_id")
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class ActivityLogViewSet(BaseOwnedModelViewSet):
    serializer_class = ActivityLogSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityLog.objects.none()

        return (
            ActivityLog.objects.filter(farm__owner=self.request.user)
            .select_related(
                "farm",
                "farm__owner",
                "field",
                "crop",
                "animal",
                "created_by",
            )
            .order_by("-date", "-created_at")
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class YieldRecordViewSet(BaseOwnedModelViewSet):
    serializer_class = YieldRecordSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return YieldRecord.objects.none()

        return (
            YieldRecord.objects.filter(farm__owner=self.request.user)
            .select_related("farm", "farm__owner", "field")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner_id != self.request.user.id:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class UserProfileViewSet(BaseOwnedModelViewSet):
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserProfile.objects.none()

        return UserProfile.objects.filter(user=self.request.user).select_related("user")

    def perform_create(self, serializer):
        if UserProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError({"detail": "Profile already exists for this user."})
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.id:
            raise ValidationError({"detail": "You can update only your own profile."})
        serializer.save()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        _get_or_create_profile(user)

        return Response(
            {
                "detail": "User registered successfully.",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Logged out successfully."}, status=status.HTTP_200_OK
        )


class PredictYieldView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        record = get_object_or_404(
            YieldRecord.objects.select_related("farm", "farm__owner", "field"),
            pk=pk,
            farm__owner=request.user,
        )

        try:
            prediction = predict_yield_for_record(record)
        except FileNotFoundError as exc:
            return Response(
                {"error": "ML model is not available", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as exc:
            return Response(
                {"error": "Prediction failed", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(prediction, status=status.HTTP_200_OK)


class FieldWateringStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        field = get_object_or_404(
            Field.objects.select_related("farm", "farm__owner"),
            pk=pk,
            farm__owner=request.user,
        )

        try:
            # Prefer new weather app if available
            from weather.services import create_irrigation_recommendation_for_field

            recommendation = create_irrigation_recommendation_for_field(field)
            return Response(
                {
                    "field_id": field.id,
                    "field_name": field.name,
                    "status": recommendation.status,
                    "severity": recommendation.severity,
                    "recommendation": recommendation.recommendation,
                    "reason": recommendation.reason,
                    "recommended_time": recommendation.recommended_time,
                    "rain_next_24h_mm": recommendation.rain_next_24h_mm,
                    "rain_next_72h_mm": recommendation.rain_next_72h_mm,
                    "evapotranspiration_24h": recommendation.evapotranspiration_24h,
                    "evidence": recommendation.evidence,
                    "source": "weather_app",
                },
                status=status.HTTP_200_OK,
            )
        except ImportError:
            pass
        except Exception as exc:
            return Response(
                {"error": "Weather recommendation failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Fallback to legacy irrigation logic
        lat = field.latitude
        lon = field.longitude
        if lat is None or lon is None:
            return Response(
                {
                    "error": "Field location is not set.",
                    "detail": "Set field latitude/longitude or polygon first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            weather_data = get_field_weather_forecast(float(lat), float(lon))
            result = calculate_watering_status(weather_data)
        except Exception as exc:
            return Response(
                {"error": "Weather request failed", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "field_id": field.id,
                "field_name": field.name,
                "source": "legacy_irrigation_service",
                **result,
            },
            status=status.HTTP_200_OK,
        )


class IoTDevicesTelemetryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from soil_monitoring.models import SoilMeasurement

        fields_qs = Field.objects.filter(farm__owner=request.user).only("id")
        field_ids = list(fields_qs.values_list("id", flat=True))

        if not field_ids:
            return Response(
                {
                    "device_count": 0,
                    "telemetry_online": 0,
                    "devices": [],
                },
                status=status.HTTP_200_OK,
            )

        ordered_readings = SoilMeasurement.objects.filter(
            field_id__in=field_ids
        ).order_by("field_id", "-sample_date", "-created_at")

        devices = []
        online_count = 0
        seen_fields = set()

        for reading in ordered_readings:
            if reading.field_id in seen_fields:
                continue
            seen_fields.add(reading.field_id)
            has_payload = any(
                value is not None
                for value in [
                    reading.moisture_percent,
                    reading.ph_level,
                    reading.nitrogen,
                    reading.phosphorus,
                    reading.potassium,
                    reading.temperature_celsius,
                ]
            )
            if has_payload:
                online_count += 1

            devices.append(
                {
                    "device_id": f"soil-field-{reading.field_id}",
                    "device_name": f"Soil moisture sensor #{reading.field_id}",
                    "field_id": reading.field_id,
                    "sample_date": str(reading.sample_date),
                    "telemetry": {
                        "moisture_percent": reading.moisture_percent,
                        "ph_level": reading.ph_level,
                        "nitrogen": reading.nitrogen,
                        "phosphorus": reading.phosphorus,
                        "potassium": reading.potassium,
                        "temperature_celsius": reading.temperature_celsius,
                    },
                    "status": "online" if has_payload else "offline",
                }
            )

        return Response(
            {
                "device_count": len(devices),
                "telemetry_online": online_count,
                "devices": devices,
            },
            status=status.HTTP_200_OK,
        )


class AIAnalyzeView(APIView):
    permission_classes = [IsAuthenticated]

    def _detect_intent(self, question: str) -> str:
        q = (question or "").lower()

        water_keywords = {
            "water",
            "watering",
            "irrigation",
            "полив",
            "вода",
            "влаж",
            "погода",
            "weather",
            "forecast",
            "прогноз",
            "дожд",
            "drain",
            "дренаж",
        }
        ndvi_keywords = {"ndvi", "вегетац", "культур", "crop", "satellite", "спутник"}
        animal_keywords = {"animal", "livestock", "живот", "скот", "здоров"}
        greeting_keywords = {
            "привет",
            "здравствуйте",
            "hello",
            "hi",
            "ассистент",
            "помощ",
        }

        if any(k in q for k in greeting_keywords):
            return "greeting"

        if any(k in q for k in water_keywords):
            return "water"
        if any(k in q for k in ndvi_keywords):
            return "ndvi"
        if any(k in q for k in animal_keywords):
            return "animals"
        return "general"

    def _format_general_answer(
        self,
        question: str,
        total_farms: int,
        total_fields: int,
        total_animals: int,
        total_crops: int,
        telemetry_online: int,
        telemetry_total: int,
    ) -> str:
        if question:
            return (
                f"По вашему запросу: '{question}'. "
                f"Сейчас в системе {total_farms} ферм, {total_fields} полей, "
                f"{total_animals} животных и {total_crops} культур. "
                f"Телеметрия доступна для {telemetry_online} из {telemetry_total} устройств."
            )

        return (
            "Вопрос не распознан, поэтому даю краткий авто-анализ: "
            f"{total_farms} ферм, {total_fields} полей, {total_animals} животных, "
            f"{total_crops} культур. "
            f"Телеметрия онлайн: {telemetry_online}/{telemetry_total}. "
            "Уточните вопрос про полив, NDVI или здоровье животных для более точного ответа."
        )

    def _format_water_answer(
        self, request, telemetry_online: int, telemetry_total: int
    ) -> str:
        fields = Field.objects.filter(farm__owner=request.user).select_related("farm")
        statuses = []
        for field in fields[:5]:
            try:
                from weather.services import create_irrigation_recommendation_for_field

                rec = create_irrigation_recommendation_for_field(field)
                statuses.append(f"{field.name}: {rec.status}")
            except Exception:
                statuses.append(f"{field.name}: no_data")

        status_text = ", ".join(statuses) if statuses else "нет данных по полям"
        return (
            "Фокус по воде: проверьте поля со статусами watch/rain_expected/no_need и скорректируйте полив по погоде. "
            f"Телеметрия онлайн: {telemetry_online}/{telemetry_total}. "
            f"Текущие статусы полей: {status_text}."
        )

    def _format_ndvi_answer(self, request) -> str:
        from ndvi.models import NDVIRecord

        fields_qs = Field.objects.filter(farm__owner=request.user)
        field_ids = list(fields_qs.values_list("id", flat=True))
        ndvi_count = NDVIRecord.objects.filter(field_id__in=field_ids).count()
        fields_with_ndvi = (
            NDVIRecord.objects.filter(field_id__in=field_ids)
            .values("field_id")
            .distinct()
            .count()
        )
        missing = max(len(field_ids) - fields_with_ndvi, 0)

        return (
            "По NDVI: используйте свежие окна дат и обновляйте данные перед анализом тренда. "
            f"Записей NDVI: {ndvi_count}. Полей с NDVI: {fields_with_ndvi}/{len(field_ids)}. "
            f"Полей без NDVI: {missing}."
        )

    def _format_animals_answer(self, animal_status: dict) -> str:
        good = animal_status.get("good", 0)
        sick = animal_status.get("sick", 0)
        critical = animal_status.get("critical", 0)
        return (
            "По животным: приоритет у групп sick/critical, для good — плановый мониторинг. "
            f"Распределение: good={good}, sick={sick}, critical={critical}."
        )

    def _build_recommendations(
        self,
        intent: str,
        answer: str,
        telemetry_online: int,
        telemetry_total: int,
    ) -> list[dict]:
        base = {
            "type": "ai_recommendation",
            "title": "AI recommendation",
            "severity": "medium",
            "priority": "medium",
            "message": answer,
        }

        if intent == "water":
            base.update(
                {
                    "severity": (
                        "high" if telemetry_online < telemetry_total else "medium"
                    ),
                    "priority": (
                        "high" if telemetry_online < telemetry_total else "medium"
                    ),
                }
            )
        elif intent == "ndvi":
            base.update({"severity": "medium", "priority": "medium"})
        elif intent == "animals":
            base.update({"severity": "medium", "priority": "medium"})
        elif intent == "greeting":
            base.update({"severity": "low", "priority": "low"})

        return [base]

    def _build_suggested_questions(self, intent: str) -> list[str]:
        if intent == "water":
            return [
                "Какие поля требуют полива сегодня?",
                "Есть ли риск переувлажнения по полям?",
                "На каких полях лучше отложить полив из-за дождя?",
            ]
        if intent == "ndvi":
            return [
                "На каких полях нет свежего NDVI?",
                "Где просадка NDVI за последнюю неделю?",
                "Какие поля в зоне риска по культурам?",
            ]
        if intent == "animals":
            return [
                "Сколько животных в статусе sick и critical?",
                "Каким группам животных нужен приоритетный осмотр?",
                "Есть ли ухудшение по здоровью животных?",
            ]
        return [
            "Какие главные риски по воде сейчас?",
            "Какие поля без NDVI в текущем окне?",
            "Сколько телеметрии онлайн по устройствам?",
        ]

    def _build_response(self, request, question: str):
        question = (question or "").strip()

        farms_qs = Farm.objects.filter(owner=request.user)
        fields_qs = Field.objects.filter(farm__owner=request.user)
        animals_qs = Animal.objects.filter(farm__owner=request.user)
        crops_qs = Crop.objects.filter(field__farm__owner=request.user)

        total_farms = farms_qs.count()
        total_fields = fields_qs.count()
        total_animals = animals_qs.count()
        total_crops = crops_qs.count()

        crop_status = crops_qs.aggregate(
            growing=Count("id", filter=Q(status="growing")),
            harvested=Count("id", filter=Q(status="harvested")),
            planned=Count("id", filter=Q(status="planned")),
        )
        animal_status = animals_qs.aggregate(
            good=Count("id", filter=Q(health_status="good")),
            sick=Count("id", filter=Q(health_status="sick")),
            critical=Count("id", filter=Q(health_status="critical")),
        )

        # Reuse IoT telemetry summary so frontend gets stable structure.
        telemetry_payload = IoTDevicesTelemetryView().get(request).data
        telemetry_online = telemetry_payload.get("telemetry_online", 0)
        telemetry_total = telemetry_payload.get("device_count", 0)

        intent = self._detect_intent(question)

        if intent == "water":
            answer = self._format_water_answer(
                request, telemetry_online, telemetry_total
            )
        elif intent == "ndvi":
            answer = self._format_ndvi_answer(request)
        elif intent == "animals":
            answer = self._format_animals_answer(animal_status)
        elif intent == "greeting":
            answer = (
                "Готов помочь с анализом фермы. Спросите про полив, NDVI, здоровье животных "
                "или качество телеметрии — дам краткие приоритеты и действия."
            )
        else:
            answer = self._format_general_answer(
                question=question,
                total_farms=total_farms,
                total_fields=total_fields,
                total_animals=total_animals,
                total_crops=total_crops,
                telemetry_online=telemetry_online,
                telemetry_total=telemetry_total,
            )

        recommendations = self._build_recommendations(
            intent=intent,
            answer=answer,
            telemetry_online=telemetry_online,
            telemetry_total=telemetry_total,
        )
        suggested_questions = self._build_suggested_questions(intent)

        return Response(
            {
                "ok": True,
                "intent": intent,
                "question": question,
                "answer": answer,
                "short_analysis": answer,
                "recommendations": recommendations,
                "suggested_questions": suggested_questions,
                "metrics": {
                    "farms": total_farms,
                    "fields": total_fields,
                    "animals": total_animals,
                    "crops": total_crops,
                    "telemetry_online": telemetry_online,
                    "telemetry_total": telemetry_total,
                },
                "breakdown": {
                    "crops": crop_status,
                    "animals": animal_status,
                },
                "telemetry": telemetry_payload,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        question = (
            request.data.get("question")
            or request.data.get("query")
            or request.data.get("message")
            or ""
        )
        return self._build_response(request, question)

    def get(self, request):
        question = (
            request.query_params.get("question") or request.query_params.get("q") or ""
        )
        return self._build_response(request, question)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()

        # Return generic message even if email does not exist
        if not user:
            return Response(
                {"detail": "If the email exists, a reset code has been sent."},
                status=status.HTTP_200_OK,
            )

        code = _generate_otp_code()
        code_hash = _otp_hash(code)
        expires_at = timezone.now() + timedelta(minutes=10)

        EmailOTP.objects.filter(email__iexact=email, used=False).update(used=True)

        EmailOTP.objects.create(
            user=user,
            email=email,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts_left=5,
            used=False,
        )

        try:
            _send_password_reset_email(email, code)
        except Exception as exc:
            return Response(
                {"error": "Failed to send reset email", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"detail": "If the email exists, a reset code has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        otp = (
            EmailOTP.objects.select_for_update()
            .filter(email__iexact=email, used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp:
            return Response(
                {"detail": "No active reset code found for this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.is_expired():
            otp.used = True
            otp.save(update_fields=["used"])
            return Response(
                {"detail": "Reset code has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.attempts_left <= 0:
            otp.used = True
            otp.save(update_fields=["used"])
            return Response(
                {"detail": "No attempts left for this reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.code_hash != _otp_hash(code):
            otp.attempts_left -= 1
            otp.save(update_fields=["attempts_left"])
            return Response(
                {"detail": "Invalid reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = otp.user
        user.set_password(new_password)
        user.save(update_fields=["password"])

        otp.used = True
        otp.save(update_fields=["used"])

        return Response(
            {"detail": "Password reset successful."},
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    profile = _get_or_create_profile(request.user)
    return Response(
        {
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "profile": UserProfileSerializer(
                profile, context={"request": request}
            ).data,
        }
    )
