from django.contrib import admin
<<<<<<< HEAD
from django.db.models import Count
from django.utils.html import mark_safe

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile


# ===== Inlines =====
class FieldInline(admin.TabularInline):
    model = Field
    extra = 0
    fields = ("name", "area", "soil_type", "coords_display", "location_text")
    readonly_fields = ("coords_display",)
    show_change_link = True

    def coords_display(self, obj):
        if obj.latitude is None or obj.longitude is None:
            return "-"
        return f"{obj.latitude}, {obj.longitude}"

    coords_display.short_description = "Coords"


class AnimalInline(admin.TabularInline):
    model = Animal
    extra = 0
    fields = ("species", "tag_id", "health_status", "birth_date")
    show_change_link = True


class ActivityInline(admin.TabularInline):
    model = ActivityLog
    extra = 0
    fields = ("activity_type", "date", "description")
    show_change_link = True


# ===== Farm =====
=======

from .models import (
    Farm,
    Field,
    Crop,
    Animal,
    ActivityLog,
    YieldRecord,
    UserProfile,
    EmailOTP,
)


>>>>>>> master
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
<<<<<<< HEAD
    list_per_page = 20

    inlines = [FieldInline, AnimalInline, ActivityInline]
    list_select_related = ("owner",)

    fieldsets = (
        ("Basic info", {"fields": ("owner", "name", "location")}),
        ("Details", {"fields": ("size_hectares",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Faster counts in list_display (avoid N+1)
        return qs.annotate(
            _fields_count=Count("fields", distinct=True),
            _animals_count=Count("animals", distinct=True),
        )

    def fields_count(self, obj):
        return getattr(obj, "_fields_count", obj.fields.count())

    fields_count.short_description = "Fields"

    def animals_count(self, obj):
        return getattr(obj, "_animals_count", obj.animals.count())

    animals_count.short_description = "Animals"


# ===== Field =====
@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("name", "farm", "area", "soil_type", "coords_display", "location_text")
    list_filter = ("soil_type", "farm")
    search_fields = ("name", "farm__name")
    ordering = ("farm", "name")
    list_per_page = 20

    list_select_related = ("farm", "farm__owner")

    fieldsets = (
        ("Field info", {"fields": ("farm", "name", "area")}),
        ("Soil", {"fields": ("soil_type",)}),
        ("Location (GPS)", {"fields": ("latitude", "longitude", "location_text")}),
    )

    def coords_display(self, obj):
        if obj.latitude is None or obj.longitude is None:
            return "-"
        return f"{obj.latitude}, {obj.longitude}"

    coords_display.short_description = "Coords"


# ===== Crop =====
@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "field", "status", "plant_date", "expected_harvest_date")
    list_filter = ("status", "plant_date", "expected_harvest_date")
    search_fields = ("name", "field__name")
    date_hierarchy = "plant_date"
    ordering = ("-plant_date",)
    list_per_page = 20

    list_select_related = ("field", "field__farm")

    fieldsets = (
        ("Basic info", {"fields": ("field", "name", "status")}),
        ("Dates", {"fields": ("plant_date", "expected_harvest_date")}),
    )


# ===== Animal =====
=======


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "farm", "area", "soil_type")
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


>>>>>>> master
@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("id", "species", "tag_id", "farm", "health_status", "birth_date")
    search_fields = ("species", "tag_id", "farm__name")
    list_filter = ("health_status", "species")
    ordering = ("species", "tag_id")
<<<<<<< HEAD
    list_per_page = 20

    list_select_related = ("farm", "farm__owner")

    fieldsets = (
        ("Identity", {"fields": ("farm", "species", "tag_id")}),
        ("Health & dates", {"fields": ("health_status", "birth_date")}),
    )


# ===== ActivityLog =====
=======


>>>>>>> master
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
<<<<<<< HEAD
    list_filter = ("activity_type", "date", "farm")
    search_fields = ("description", "farm__name", "created_by__username")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")
    list_per_page = 20

    list_select_related = ("farm", "farm__owner", "field", "crop", "animal", "created_by")

    fieldsets = (
        ("Activity", {"fields": ("farm", "date", "activity_type", "description")}),
        ("Related objects", {"fields": ("field", "crop", "animal")}),
        ("Audit", {"fields": ("created_by",)}),
    )
    readonly_fields = ("created_by", "created_at")

    def related_object(self, obj):
        if obj.field_id:
            return f"Field: {obj.field.name}"
        if obj.crop_id:
            return f"Crop: {obj.crop.name}"
        if obj.animal_id:
            return f"Animal: {obj.animal.tag_id}"
        return "-"

    related_object.short_description = "Related to"


# ===== UserProfile (with avatar preview) =====
=======
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


>>>>>>> master
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone")
    search_fields = ("user__username", "user__email", "phone")

<<<<<<< HEAD
    list_select_related = ("user",)

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Profile", {"fields": ("avatar_preview", "avatar", "bio", "phone")}),
    )

    def avatar_preview(self, obj):
        if obj.avatar and hasattr(obj.avatar, "url"):
            return mark_safe(
                f'<img src="{obj.avatar.url}" width="40" height="40" '
                f'style="object-fit: cover; border-radius: 50%; border: 1px solid #ccc;" />'
            )
        return "-"

    avatar_preview.short_description = "Avatar"


# ===== Global admin branding =====
admin.site.site_header = "Farm Management Admin"
admin.site.site_title = "Farm Admin"
admin.site.index_title = "Farm Management Dashboard"
=======

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
>>>>>>> master
