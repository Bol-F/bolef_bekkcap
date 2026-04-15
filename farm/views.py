from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
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
from .models import ActivityLog, Animal, Crop, EmailOTP, Farm, Field, UserProfile, YieldRecord
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

        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


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
            "profile": UserProfileSerializer(profile, context={"request": request}).data,
        }
    )