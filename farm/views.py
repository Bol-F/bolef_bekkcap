from rest_framework import viewsets, permissions

from .models import Farm, Field, Crop, Animal, ActivityLog, UserProfile
from .serializers import (
    FarmSerializer,
    FieldSerializer,
    CropSerializer,
    AnimalSerializer,
    ActivityLogSerializer,
    UserProfileSerializer,
)


class IsOwnerRelatedPermission(permissions.BasePermission):
    """
    Simple permission: user must be authenticated and
    related to the object via farm.owner or object.user/owner.
    """

    def has_permission(self, request, view):
        # Only authenticated users can access viewsets
        return request.user and request.user.is_authenticated

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
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            # important for swagger / anonymous schema generation
            return Farm.objects.none()
        return Farm.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class FieldViewSet(viewsets.ModelViewSet):
    serializer_class = FieldSerializer
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Field.objects.none()
        # only fields from farms that belong to current user
        return Field.objects.filter(farm__owner=user)


class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Crop.objects.none()
        return Crop.objects.filter(field__farm__owner=user)


class AnimalViewSet(viewsets.ModelViewSet):
    serializer_class = AnimalSerializer
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Animal.objects.none()
        return Animal.objects.filter(farm__owner=user)


class ActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(farm__owner=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):
    serializer_class = UserProfileSerializer
    permission_classes = [IsOwnerRelatedPermission]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return UserProfile.objects.none()
        # each user only sees their own profile
        return UserProfile.objects.filter(user=user)

    def perform_create(self, serializer):
        # allow creating only one profile per user
        serializer.save(user=self.request.user)
