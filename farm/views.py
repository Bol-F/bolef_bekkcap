from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile
from .serializers import (
    ActivityLogSerializer,
    AnimalSerializer,
    CropSerializer,
    FarmSerializer,
    FieldSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)


class IsOwnerRelatedPermission(permissions.BasePermission):
    """
    Объектный доступ: пользователь должен быть владельцем фермы/поля/животного/профиля.
    """

    def has_permission(self, request, view):
        # Для ViewSet'ов — только аутентифицированные
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile

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
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return Farm.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return Field.objects.filter(farm__owner=self.request.user)


class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return Crop.objects.filter(field__farm__owner=self.request.user)


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return Animal.objects.filter(farm__owner=self.request.user)


class ActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return ActivityLog.objects.filter(farm__owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if UserProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError("Profile for this user already exists.")
        serializer.save(user=self.request.user)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    JWT logout: ожидает 'refresh' и добавляет его в blacklist.
    """

    permission_classes = [permissions.IsAuthenticated]

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
            {"message": "Logged out"},
            status=status.HTTP_205_RESET_CONTENT,
        )
