from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny

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
    Object-level permission to only allow owners of an object to access it.
    """

    def has_permission(self, request, view):
        # Only authenticated users can access (except for safe methods in ActivityLogViewSet)
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Import here to avoid potential circular imports
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
        if getattr(self, 'swagger_fake_view', False):
            return Farm.objects.none()

        return Farm.objects.filter(owner=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Field.objects.none()
        return Field.objects.filter(farm__owner=self.request.user).select_related('farm')


class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Crop.objects.none()

        return Crop.objects.filter(
            field__farm__owner=self.request.user
        ).select_related('field', 'field__farm')


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Animal.objects.none()

        return Animal.objects.filter(
            farm__owner=self.request.user
        ).select_related('farm')


class ActivityLogViewSet(viewsets.ModelViewSet):
    """
    Activity Log endpoint.

    GET: Accessible to all (including anonymous) - returns empty for anonymous
    POST/PUT/PATCH/DELETE: Only authenticated owners
    """

    serializer_class = ActivityLogSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsOwnerRelatedPermission()]

    def get_queryset(self):
        # Optimize queries with select_related
        queryset = ActivityLog.objects.select_related(
            'farm', 'field', 'crop', 'animal', 'created_by'
        )

        user = self.request.user
        if user.is_authenticated:
            return queryset.filter(farm__owner=user).order_by('-date', '-created_at')
        return ActivityLog.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerRelatedPermission]
    http_method_names = ['get', 'put', 'patch']  # Don't allow delete or post

    def get_queryset(self):
        # Handle schema generation
        if getattr(self, 'swagger_fake_view', False):
            return UserProfile.objects.none()

        return UserProfile.objects.filter(user=self.request.user).select_related('user')

    def perform_create(self, serializer):
        # Check if profile already exists
        if UserProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError({"detail": "Profile already exists for this user."})
        serializer.save(user=self.request.user)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens for immediate login
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """
    JWT logout: blacklists the refresh token.
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
            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )