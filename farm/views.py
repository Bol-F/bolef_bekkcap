from allauth.account.models import EmailAddress
from rest_framework import permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile
from .serializers import (
    ActivityLogSerializer,
    AnimalSerializer,
    CropSerializer,
    FarmSerializer,
    FieldSerializer,
    UserProfileSerializer,
)


# OPTIONAL: если хочешь сразу отправлять OTP при регистрации


class IsOwnerRelatedPermission(permissions.BasePermission):
    """
    Object-level access: user must own farm-related objects or their own profile.
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
        return Farm.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Field.objects.none()
        return Field.objects.filter(farm__owner=self.request.user)


class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Crop.objects.none()
        return Crop.objects.filter(field__farm__owner=self.request.user)


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Animal.objects.none()
        return Animal.objects.filter(farm__owner=self.request.user)


class ActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(farm__owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


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


# farm/views.py

from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer
from .email_otp_views import create_and_send_otp  # путь поправь, если файл иначе называется


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        # (Опционально) если хочешь запретить логин до верификации:
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
    verified = EmailAddress.objects.filter(
        user=user, email=user.email, verified=True
    ).exists()

    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "email_verified": verified,
        }
    )
