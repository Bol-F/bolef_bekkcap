from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Farm, Field, Crop, Animal, ActivityLog
from .models import UserProfile

User = get_user_model()


class FarmSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Farm
        fields = [
            "id",
            "owner",
            "name",
            "location",
            "size_hectares",
            "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]


class FieldSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())

    class Meta:
        model = Field
        fields = [
            "id",
            "farm",
            "name",
            "area",
            "soil_type",
        ]
        read_only_fields = ["id"]


class CropSerializer(serializers.ModelSerializer):
    field = serializers.PrimaryKeyRelatedField(queryset=Field.objects.all())
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Crop
        fields = [
            "id",
            "field",
            "name",
            "plant_date",
            "expected_harvest_date",
            "status",
            "status_display",
        ]
        read_only_fields = ["id", "status_display"]


class AnimalSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())
    health_status_display = serializers.CharField(
        source="get_health_status_display",
        read_only=True,
    )

    class Meta:
        model = Animal
        fields = [
            "id",
            "farm",
            "species",
            "tag_id",
            "birth_date",
            "health_status",
            "health_status_display",
        ]
        read_only_fields = ["id", "health_status_display"]


class ActivityLogSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())
    field = serializers.PrimaryKeyRelatedField(
        queryset=Field.objects.all(),
        required=False,
        allow_null=True,
    )
    crop = serializers.PrimaryKeyRelatedField(
        queryset=Crop.objects.all(),
        required=False,
        allow_null=True,
    )
    animal = serializers.PrimaryKeyRelatedField(
        queryset=Animal.objects.all(),
        required=False,
        allow_null=True,
    )
    created_by = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "farm",
            "date",
            "activity_type",
            "description",
            "field",
            "crop",
            "animal",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = UserProfile
        fields = ["id", "user", "avatar", "bio", "phone"]
        read_only_fields = ["id", "user"]
