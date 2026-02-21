# farm/views.py

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import permissions, status
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .email_otp_views import create_and_send_otp
from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile
from .serializers import (
    ActivityLogSerializer,
    AnimalSerializer,
    CropSerializer,
    FarmSerializer,
    FieldSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()


class IsOwnerRelatedPermission(permissions.BasePermission):
    """
    Object-level access:
    - Farm: owner only
    - Field: owner of field.farm
    - Crop: owner of crop.field.farm
    - Animal: owner of animal.farm
    - ActivityLog: owner of log.farm
    - UserProfile: profile owner only
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user

        if isinstance(obj, Farm):
            return obj.owner == user
        if isinstance(obj, Field):
            return obj.farm.owner == user
        if isinstance(obj, Crop):
            return obj.field.farm.owner == user
        if isinstance(obj, Animal):
            return obj.farm.owner == user
        if isinstance(obj, ActivityLog):
            return obj.farm.owner == user
        if isinstance(obj, UserProfile):
            return obj.user == user

        return False


class FarmViewSet(viewsets.ModelViewSet):
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Farm.objects.none()
        return Farm.objects.filter(owner=self.request.user).select_related("owner")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        # owner must stay same
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Field.objects.none()
        return Field.objects.filter(farm__owner=self.request.user).select_related(
            "farm", "farm__owner"
        )

    def perform_create(self, serializer):
        # Farm queryset already filtered in serializer __init__,
        # but keep hard check for safety.
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Crop.objects.none()
        return Crop.objects.filter(field__farm__owner=self.request.user).select_related(
            "field", "field__farm", "field__farm__owner"
        )

    def perform_create(self, serializer):
        field = serializer.validated_data.get("field")
        if not field or field.farm.owner != self.request.user:
            raise ValidationError({"field": "You do not own this field/farm."})
        serializer.save()

    def perform_update(self, serializer):
        field = serializer.validated_data.get("field", serializer.instance.field)
        if not field or field.farm.owner != self.request.user:
            raise ValidationError({"field": "You do not own this field/farm."})
        serializer.save()


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Animal.objects.none()
        return Animal.objects.filter(farm__owner=self.request.user).select_related(
            "farm", "farm__owner"
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class ActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(farm__owner=self.request.user).select_related(
            "farm",
            "farm__owner",
            "field",
            "crop",
            "animal",
            "created_by",
        )

    def perform_create(self, serializer):
        # Your serializer.validate() already checks field/crop/animal belong to same farm.
        farm = serializer.validated_data.get("farm")
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})
        serializer.save()


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UserProfile.objects.none()
        return UserProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if UserProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError("Profile for this user already exists.")
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Optional: lock account until email verification
        user.is_active = False
        user.save(update_fields=["is_active"])

        sent = create_and_send_otp(user)

        if not sent:
            return Response(
                {
                    "detail": "Registered, but email sending failed. You can request a new code.",
                    "email": user.email,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "detail": "Registered. Verification code sent to email.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """
    JWT logout: expects {"refresh": "..."} and blacklists it.
    Requires: 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS + migrations.
    """

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

        return Response({"message": "Logged out"}, status=status.HTTP_205_RESET_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user

    # If you use django-allauth:
    # from allauth.account.models import EmailAddress
    # verified = EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists()

    # If you have your own OTP/email verification model, replace this logic:
    verified = getattr(user, "email_verified", False)

    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "email_verified": bool(verified),
        }
    )


class PasswordResetRequestView(APIView):
    """
    POST: {"email": "..."}
    Sends a code to email (if user exists). Always returns 200 for security.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # 6-digit code
        code = f"{secrets.randbelow(10 ** 6):06d}"
        cache_key = f"pwdreset:{email}"
        cache.set(cache_key, code, timeout=10 * 60)  # 10 minutes

        # SECURITY: don't reveal whether user exists
        subject = "Password reset code"
        message = f"Your password reset code: {code}\nThis code expires in 10 minutes."

        try:
            # send only if user exists (optional)
            if User.objects.filter(email__iexact=email).exists():
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,  # для дебага лучше False
                )
        except Exception:
            # чтобы не падало 500 даже если SMTP сломался
            return Response(
                {
                    "detail": "If this email exists, a reset code was sent (email sending may fail)."
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"detail": "If this email exists, a reset code was sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    POST: {"email":"...", "code":"123456", "new_password":"...", "new_password2":"..."}
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        cache_key = f"pwdreset:{email}"
        saved_code = cache.get(cache_key)

        if not saved_code or saved_code != code:
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            # по идее сюда не попадешь, но оставим безопасно
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        cache.delete(cache_key)

        return Response(
            {"detail": "Password updated successfully."}, status=status.HTTP_200_OK
        )
