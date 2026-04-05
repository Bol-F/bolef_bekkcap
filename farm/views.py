<<<<<<< HEAD
# farm/views.py (overwrite)

=======
>>>>>>> master
import secrets
from django.shortcuts import get_object_or_404
from .ml_service import predict_yield_for_record
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
<<<<<<< HEAD

=======
>>>>>>> master
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

<<<<<<< HEAD
from allauth.account.models import EmailAddress

from .email_otp_views import create_and_send_otp, _hash  # _hash used to compare codes
from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile, EmailOTP
=======
from .email_otp_views import create_and_send_otp
from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile, YieldRecord
>>>>>>> master
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


class IsOwnerRelatedPermission(permissions.BasePermission):
<<<<<<< HEAD
=======
    """
    Object-level access:
    - Farm: owner only
    - Field: owner of field.farm
    - Crop: owner of crop.field.farm
    - Animal: owner of animal.farm
    - ActivityLog: owner of log.farm
    - YieldRecord: owner of record.farm
    - UserProfile: profile owner only
    """

>>>>>>> master
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if isinstance(obj, Farm):
            return obj.owner_id == user.id
        if isinstance(obj, Field):
            return obj.farm.owner_id == user.id
        if isinstance(obj, Crop):
            return obj.field.farm.owner_id == user.id
        if isinstance(obj, Animal):
            return obj.farm.owner_id == user.id
        if isinstance(obj, ActivityLog):
<<<<<<< HEAD
            return obj.farm.owner_id == user.id
=======
            return obj.farm.owner == user
        if isinstance(obj, YieldRecord):
            return obj.farm.owner == user
>>>>>>> master
        if isinstance(obj, UserProfile):
            return obj.user_id == user.id
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
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Field.objects.none()
<<<<<<< HEAD
        return Field.objects.filter(farm__owner=self.request.user).select_related("farm", "farm__owner")
=======
        return Field.objects.filter(farm__owner=self.request.user).select_related(
            "farm", "farm__owner"
        )
>>>>>>> master

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
        if not field or field.farm.owner_id != self.request.user.id:
            raise ValidationError({"field": "You do not own this field/farm."})
        serializer.save()

    def perform_update(self, serializer):
        field = serializer.validated_data.get("field", serializer.instance.field)
        if not field or field.farm.owner_id != self.request.user.id:
            raise ValidationError({"field": "You do not own this field/farm."})
        serializer.save()


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Animal.objects.none()
<<<<<<< HEAD
        return Animal.objects.filter(farm__owner=self.request.user).select_related("farm", "farm__owner")
=======
        return Animal.objects.filter(farm__owner=self.request.user).select_related(
            "farm", "farm__owner"
        )
>>>>>>> master

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


class ActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(farm__owner=self.request.user).select_related(
<<<<<<< HEAD
            "farm", "farm__owner", "field", "crop", "animal", "created_by"
=======
            "farm",
            "farm__owner",
            "field",
            "crop",
            "animal",
            "created_by",
>>>>>>> master
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


class YieldRecordViewSet(viewsets.ModelViewSet):
    serializer_class = YieldRecordSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return YieldRecord.objects.none()
        return (
            YieldRecord.objects.filter(farm__owner=self.request.user)
            .select_related("farm", "farm__owner", "field", "field__farm")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        farm = serializer.validated_data.get("farm")
        field = serializer.validated_data.get("field")

        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})

        if field and field.farm_id != farm.id:
            raise ValidationError({"field": "Field does not belong to the selected farm."})

        serializer.save()

    def perform_update(self, serializer):
        farm = serializer.validated_data.get("farm", serializer.instance.farm)
        field = serializer.validated_data.get("field", serializer.instance.field)

        if not farm or farm.owner != self.request.user:
            raise ValidationError({"farm": "You do not own this farm."})

        if field and field.farm_id != farm.id:
            raise ValidationError({"field": "Field does not belong to the selected farm."})

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

        user.is_active = False
        user.save(update_fields=["is_active"])

        sent = create_and_send_otp(user, purpose=EmailOTP.Purpose.VERIFY_EMAIL)

        if not sent:
            return Response(
                {"detail": "Registered, but email sending failed. You can request a new code.", "email": user.email},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"detail": "Registered. Verification code sent to email.", "email": user.email},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Logged out"}, status=status.HTTP_205_RESET_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
<<<<<<< HEAD
    verified = EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists()
=======
    email = (getattr(user, "email", "") or "").strip().lower()

    verified = False
    if email:
        verified = EmailAddress.objects.filter(
            user=user,
            email__iexact=email,
            verified=True,
        ).exists()

>>>>>>> master
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "email_verified": verified,
        }
    )


class PasswordResetRequestView(APIView):
<<<<<<< HEAD
    """
    POST: {"email": "..."}
    Sends RESET_PASSWORD OTP to email (if user exists).
    Always returns 200 to avoid user enumeration.
    """
=======
>>>>>>> master
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

<<<<<<< HEAD
        user = User.objects.filter(email__iexact=email).order_by("-id").first()
        if user:
            # send reset OTP (separate from verify OTP)
            create_and_send_otp(user, purpose=EmailOTP.Purpose.RESET_PASSWORD)
=======
        code = f"{secrets.randbelow(10**6):06d}"
        cache_key = f"pwdreset:{email}"
        cache.set(cache_key, code, timeout=10 * 60)

        subject = "Password reset code"
        message = f"Your password reset code: {code}\nThis code expires in 10 minutes."

        try:
            if User.objects.filter(email__iexact=email).exists():
                send_mail(
                    subject,
                    message,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None)
                    or getattr(settings, "EMAIL_HOST_USER", None),
                    [email],
                    fail_silently=False,
                )
        except Exception:
            return Response(
                {
                    "detail": "If this email exists, a reset code was sent (email sending may fail)."
                },
                status=status.HTTP_200_OK,
            )
>>>>>>> master

        return Response(
            {"detail": "If this email exists, a reset code was sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
<<<<<<< HEAD
    """
    POST: {"email":"...", "code":"123456", "new_password":"...", "new_password2":"..."}
    Uses EmailOTP(purpose=RESET_PASSWORD)
    """
=======
>>>>>>> master
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        user = User.objects.filter(email__iexact=email).order_by("-id").first()
        if not user:
<<<<<<< HEAD
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        otp = (
            EmailOTP.objects.filter(
                user=user,
                email=email,
                purpose=EmailOTP.Purpose.RESET_PASSWORD,
                used=False,
=======
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
>>>>>>> master
            )
            .order_by("-created_at")
            .first()
        )
        if not otp:
            return Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_expired():
            otp.used = True
            otp.save(update_fields=["used"])
            return Response({"detail": "Code expired. Send a new code."}, status=status.HTTP_400_BAD_REQUEST)

        if otp.attempts_left <= 0:
            otp.used = True
            otp.save(update_fields=["used"])
            return Response({"detail": "Too many attempts. Send a new code."}, status=status.HTTP_400_BAD_REQUEST)

        if _hash(code) != otp.code_hash:
            otp.attempts_left -= 1
            otp.save(update_fields=["attempts_left"])
            return Response({"detail": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST)

        # success
        otp.used = True
        otp.save(update_fields=["used"])

        user.set_password(new_password)
        user.save(update_fields=["password"])

<<<<<<< HEAD
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
=======
        cache.delete(cache_key)

        return Response(
            {"detail": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )

class PredictYieldView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        record = get_object_or_404(
            YieldRecord.objects.select_related("farm"),
            pk=pk,
            farm__owner=request.user,
        )

        result = predict_yield_for_record(record)

        return Response(
            {
                "detail": "Prediction completed successfully.",
                "data": result,
            },
            status=status.HTTP_200_OK,
        )
>>>>>>> master
