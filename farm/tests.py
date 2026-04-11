from django.contrib import admin

from .models import (
    ActivityLog,
    Animal,
    Crop,
    EmailOTP,
    Farm,
    Field,
    UserProfile,
    YieldRecord,
)


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "farm_code",
        "owner",
        "location",
        "size_hectares",
        "created_at",
    )
    search_fields = ("name", "farm_code", "location", "owner__username", "owner__email")
    list_filter = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "farm", "area", "soil_type", "latitude", "longitude")
    search_fields = ("name", "farm__name")
    list_filter = ("soil_type", "farm")
    ordering = ("id",)


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "field",
        "status",
        "plant_date",
        "expected_harvest_date",
    )
    search_fields = ("name", "field__name", "field__farm__name")
    list_filter = ("status", "plant_date", "expected_harvest_date")
    ordering = ("-id",)


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("id", "species", "tag_id", "farm", "health_status", "birth_date")
    search_fields = ("species", "tag_id", "farm__name")
    list_filter = ("health_status", "species")
    ordering = ("species", "tag_id")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "activity_type",
        "farm",
        "field",
        "crop",
        "animal",
        "created_by",
        "created_at",
    )
    search_fields = (
        "description",
        "farm__name",
        "field__name",
        "crop__name",
        "animal__tag_id",
    )
    list_filter = ("activity_type", "date", "created_at")
    ordering = ("-date", "-created_at")
    readonly_fields = ("created_at",)


@admin.register(YieldRecord)
class YieldRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "farm",
        "crop_type",
        "season",
        "irrigation_type",
        "soil_type",
        "farm_area_acres",
        "actual_yield_tons",
        "predicted_yield_tons",
        "model_name",
        "created_at",
    )
    search_fields = ("farm__name", "crop_type", "model_name", "notes")
    list_filter = ("season", "irrigation_type", "soil_type", "model_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "prediction_created_at")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone")
    search_fields = ("user__username", "user__email", "phone")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "email",
        "expires_at",
        "attempts_left",
        "used",
        "created_at",
    )
    search_fields = ("email", "user__username", "user__email")
    list_filter = ("used", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
