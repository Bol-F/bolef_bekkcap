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
        "owner",
        "farm_code",
        "location",
        "size_hectares",
        "latitude",
        "longitude",
        "has_location_display",
        "created_at",
    )
    search_fields = (
        "name",
        "farm_code",
        "location",
        "owner__username",
        "owner__email",
    )
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    autocomplete_fields = ("owner",)
    readonly_fields = (
        "bbox_min_lon",
        "bbox_max_lon",
        "bbox_min_lat",
        "bbox_max_lat",
        "polygon_area_approx_ha",
        "created_at",
    )

    fieldsets = (
        (
            "Basic info",
            {
                "fields": (
                    "owner",
                    "name",
                    "farm_code",
                    "location",
                    "size_hectares",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    ("latitude", "longitude"),
                    "polygon",
                )
            },
        ),
        (
            "Derived spatial info",
            {
                "fields": (
                    ("bbox_min_lon", "bbox_max_lon"),
                    ("bbox_min_lat", "bbox_max_lat"),
                    "polygon_area_approx_ha",
                    "created_at",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Has location")
    def has_location_display(self, obj):
        return obj.has_location


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "farm",
        "soil_type",
        "area",
        "latitude",
        "longitude",
        "has_location_display",
    )
    search_fields = (
        "name",
        "farm__name",
        "farm__farm_code",
        "farm__owner__username",
        "farm__owner__email",
    )
    list_filter = ("soil_type", "farm")
    ordering = ("farm", "name")
    autocomplete_fields = ("farm",)
    readonly_fields = (
        "bbox_min_lon",
        "bbox_max_lon",
        "bbox_min_lat",
        "bbox_max_lat",
        "polygon_area_approx_ha",
    )

    fieldsets = (
        (
            "Basic info",
            {
                "fields": (
                    "farm",
                    "name",
                    "area",
                    "soil_type",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    ("latitude", "longitude"),
                    "polygon",
                )
            },
        ),
        (
            "Derived spatial info",
            {
                "fields": (
                    ("bbox_min_lon", "bbox_max_lon"),
                    ("bbox_min_lat", "bbox_max_lat"),
                    "polygon_area_approx_ha",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Has location")
    def has_location_display(self, obj):
        return obj.has_location


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "field",
        "field_farm",
        "status",
        "plant_date",
        "expected_harvest_date",
    )
    search_fields = (
        "name",
        "field__name",
        "field__farm__name",
        "field__farm__owner__username",
    )
    list_filter = ("status", "plant_date", "expected_harvest_date")
    ordering = ("-id",)
    autocomplete_fields = ("field",)

    @admin.display(description="Farm")
    def field_farm(self, obj):
        return obj.field.farm.name


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "species",
        "tag_id",
        "farm",
        "health_status",
        "birth_date",
    )
    search_fields = (
        "species",
        "tag_id",
        "farm__name",
        "farm__owner__username",
    )
    list_filter = ("health_status", "farm")
    ordering = ("species", "tag_id")
    autocomplete_fields = ("farm",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "farm",
        "activity_type",
        "date",
        "field",
        "crop",
        "animal",
        "created_by",
        "created_at",
    )
    search_fields = (
        "farm__name",
        "field__name",
        "crop__name",
        "animal__tag_id",
        "description",
        "created_by__username",
    )
    list_filter = ("activity_type", "date", "created_at")
    ordering = ("-date", "-created_at")
    autocomplete_fields = ("farm", "field", "crop", "animal", "created_by")


@admin.register(YieldRecord)
class YieldRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "farm",
        "field",
        "crop_type",
        "season",
        "irrigation_type",
        "soil_type",
        "farm_area_acres",
        "actual_yield_tons",
        "predicted_yield_tons",
        "created_at",
    )
    search_fields = (
        "crop_type",
        "farm__name",
        "field__name",
        "farm__owner__username",
        "model_name",
    )
    list_filter = (
        "season",
        "irrigation_type",
        "soil_type",
        "created_at",
    )
    ordering = ("-created_at",)
    autocomplete_fields = ("farm", "field")
    readonly_fields = (
        "predicted_yield_tons",
        "model_name",
        "confidence_score",
        "prediction_created_at",
        "created_at",
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone")
    search_fields = ("user__username", "user__email", "phone")
    autocomplete_fields = ("user",)


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
    search_fields = ("user__username", "user__email", "email")
    list_filter = ("used", "created_at", "expires_at")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
