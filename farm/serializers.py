from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile, YieldRecord

User = get_user_model()


class FarmSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Farm
        fields = ["id", "owner", "name", "location", "size_hectares", "created_at"]
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
            "latitude",
            "longitude",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["farm"].queryset = Farm.objects.filter(owner=request.user)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["farm"].queryset = Farm.objects.filter(owner=request.user)


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
        farm = attrs.get("farm") or getattr(self.instance, "farm", None)
        field = attrs.get("field") or getattr(self.instance, "field", None)
        crop = attrs.get("crop") or getattr(self.instance, "crop", None)
        animal = attrs.get("animal") or getattr(self.instance, "animal", None)

        if not farm:
            raise ValidationError({"farm": "This field is required."})

        if field and field.farm_id != farm.id:
            raise ValidationError({"field": "Field does not belong to the selected farm."})
        if crop and crop.field.farm_id != farm.id:
            raise ValidationError({"crop": "Crop does not belong to the selected farm."})
        if animal and animal.farm_id != farm.id:
            raise ValidationError({"animal": "Animal does not belong to the selected farm."})

        return attrs


class YieldRecordSerializer(serializers.ModelSerializer):
    farm = serializers.PrimaryKeyRelatedField(queryset=Farm.objects.all())
    field = serializers.PrimaryKeyRelatedField(
        queryset=Field.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = YieldRecord
        fields = [
            "id",
            "farm",
            "field",
            "crop_type",
            "season",
            "irrigation_type",
            "soil_type",
            "farm_area_acres",
            "fertilizer_used_tons",
            "pesticide_used_kg",
            "water_usage_cubic_meters",
            "actual_yield_tons",
            "predicted_yield_tons",
            "model_name",
            "confidence_score",
            "notes",
            "prediction_created_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "predicted_yield_tons",
            "model_name",
            "confidence_score",
            "prediction_created_at",
            "created_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            self.fields["farm"].queryset = Farm.objects.filter(owner=user)
            self.fields["field"].queryset = Field.objects.filter(farm__owner=user)

    def validate(self, attrs):
        farm = attrs.get("farm") or getattr(self.instance, "farm", None)
        field = attrs.get("field") or getattr(self.instance, "field", None)

        if not farm:
            raise ValidationError({"farm": "This field is required."})

        if field and field.farm_id != farm.id:
            raise ValidationError({"field": "Field does not belong to the selected farm."})

        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = UserProfile
        fields = ["id", "user", "avatar", "bio", "phone"]
        read_only_fields = ["id", "user"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "password2")
        read_only_fields = ("id",)

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if not email:
            raise serializers.ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return email

    def validate_username(self, value):
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Username is required.")
        return username

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Passwords must match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return (value or "").strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=10)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password2 = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "Passwords must match."}
            )
        validate_password(attrs["new_password"])
        attrs["email"] = (attrs["email"] or "").strip().lower()
        attrs["code"] = (attrs["code"] or "").strip()
        return attrs


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        password = attrs.get("password") or ""
        password2 = attrs.get("password2") or ""

        if password != password2:
            raise serializers.ValidationError({"password2": "Passwords do not match."})

        user = self.context["request"].user

        try:
            validate_password(password, user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        return attrs