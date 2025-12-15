from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile

User = get_user_model()


# ==========================
# Farm
# ==========================
class FarmSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Farm
        fields = ["id", "owner", "name", "location", "size_hectares", "created_at"]
        read_only_fields = ["id", "owner", "created_at"]


# ==========================
# Field
# ==========================
class FieldSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())

    class Meta:
        model = Field
        fields = ["id", "farm", "name", "area", "soil_type"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["farm"].queryset = Farm.objects.filter(owner=request.user)


# ==========================
# Crop
# ==========================
class CropSerializer(serializers.ModelSerializer):
    field = serializers.PrimaryKeyRelatedField(queryset=Field.objects.all())
    status_display = serializers.CharField(source="get_status_display", read_only=True)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["field"].queryset = Field.objects.filter(
                farm__owner=request.user
            )


# ==========================
# Animal
# ==========================
class AnimalSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())
    health_status_display = serializers.CharField(
        source="get_health_status_display", read_only=True
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["farm"].queryset = Farm.objects.filter(owner=request.user)


# ==========================
# ActivityLog
# ==========================
class ActivityLogSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())
    field = serializers.PrimaryKeyRelatedField(
        queryset=Field.objects.all(), required=False, allow_null=True
    )
    crop = serializers.PrimaryKeyRelatedField(
        queryset=Crop.objects.all(), required=False, allow_null=True
    )
    animal = serializers.PrimaryKeyRelatedField(
        queryset=Animal.objects.all(), required=False, allow_null=True
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            self.fields["farm"].queryset = Farm.objects.filter(owner=user)
            self.fields["field"].queryset = Field.objects.filter(farm__owner=user)
            self.fields["crop"].queryset = Crop.objects.filter(field__farm__owner=user)
            self.fields["animal"].queryset = Animal.objects.filter(farm__owner=user)

    def validate(self, attrs):
        """
        Rule: if field/crop/animal provided, they must belong to the same farm.
        """
        farm = attrs.get("farm")
        field = attrs.get("field")
        crop = attrs.get("crop")
        animal = attrs.get("animal")

        if field and field.farm_id != farm.id:
            raise ValidationError("Field does not belong to the selected farm.")
        if crop and crop.field.farm_id != farm.id:
            raise ValidationError("Crop does not belong to the selected farm.")
        if animal and animal.farm_id != farm.id:
            raise ValidationError("Animal does not belong to the selected farm.")

        return attrs


# ==========================
# UserProfile
# ==========================
class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = UserProfile
        fields = ["id", "user", "avatar", "bio", "phone"]
        read_only_fields = ["id", "user"]


# ==========================
# Registration (optional)
# ==========================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "password2")

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if not email:
            raise serializers.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords must match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class BaseRegisterSerializer(serializers.Serializer):
    """
    Base for registration:
    - normalizes email
    - blocks duplicate email
    """

    def validate_email(self, value: str) -> str:
        email = (value or "").strip().lower()
        if not email:
            raise serializers.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return email
