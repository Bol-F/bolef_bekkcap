# farm/admin.py
from django.contrib import admin
from django.utils.html import mark_safe

from .models import ActivityLog, Animal, Crop, Farm, Field, UserProfile

# ===== Inlines =====


class FieldInline(admin.TabularInline):
    model = Field
    extra = 0
    fields = ("name", "area", "soil_type")
    show_change_link = True


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


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "location",
        "size_hectares",
        "fields_count",
        "animals_count",
        "created_at",
    )
    list_filter = ("location", "created_at")
    search_fields = ("name", "location", "owner__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 20

    inlines = [FieldInline, AnimalInline, ActivityInline]

    fieldsets = (
        (
            "Basic info",
            {
                "fields": ("owner", "name", "location"),
            },
        ),
        (
            "Details",
            {
                "fields": ("size_hectares",),
            },
        ),
    )

    def fields_count(self, obj):
        return obj.fields.count()

    fields_count.short_description = "Fields"

    def animals_count(self, obj):
        return obj.animals.count()

    animals_count.short_description = "Animals"


# ===== Field =====


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("name", "farm", "area", "soil_type")
    list_filter = ("soil_type", "farm")
    search_fields = ("name", "farm__name")
    ordering = ("farm", "name")
    list_per_page = 20

    fieldsets = (
        (
            "Field info",
            {
                "fields": ("farm", "name", "area"),
            },
        ),
        (
            "Soil",
            {
                "fields": ("soil_type",),
            },
        ),
    )


# ===== Crop =====


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "field", "status", "plant_date", "expected_harvest_date")
    list_filter = ("status", "plant_date", "expected_harvest_date")
    search_fields = ("name", "field__name")
    date_hierarchy = "plant_date"
    ordering = ("-plant_date",)
    list_per_page = 20

    fieldsets = (
        (
            "Basic info",
            {
                "fields": ("field", "name", "status"),
            },
        ),
        (
            "Dates",
            {
                "fields": ("plant_date", "expected_harvest_date"),
            },
        ),
    )


# ===== Animal =====


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("species", "tag_id", "farm", "health_status", "birth_date")
    list_filter = ("species", "health_status", "farm")
    search_fields = ("species", "tag_id", "farm__name")
    date_hierarchy = "birth_date"
    ordering = ("species", "tag_id")
    list_per_page = 20

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("farm", "species", "tag_id"),
            },
        ),
        (
            "Health & dates",
            {
                "fields": ("health_status", "birth_date"),
            },
        ),
    )


# ===== ActivityLog =====


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "activity_type",
        "farm",
        "date",
        "related_object",
        "created_by",
        "created_at",
    )
    list_filter = ("activity_type", "date", "farm")
    search_fields = ("description", "farm__name", "created_by__username")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")
    list_per_page = 20

    fieldsets = (
        (
            "Activity",
            {
                "fields": ("farm", "date", "activity_type", "description"),
            },
        ),
        (
            "Related objects",
            {
                "fields": ("field", "crop", "animal"),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_by",),
            },
        ),
    )
    readonly_fields = ("created_by", "created_at")

    def related_object(self, obj):
        if obj.field:
            return f"Field: {obj.field.name}"
        if obj.crop:
            return f"Crop: {obj.crop.name}"
        if obj.animal:
            return f"Animal: {obj.animal.tag_id}"
        return "-"

    related_object.short_description = "Related to"


# ===== UserProfile (with avatar preview) =====


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("avatar_preview", "user", "bio", "phone")
    search_fields = ("user__username", "phone", "bio")
    list_per_page = 20
    readonly_fields = ("avatar_preview",)

    fieldsets = (
        (
            "User",
            {
                "fields": ("user",),
            },
        ),
        (
            "Profile",
            {
                "fields": ("avatar_preview", "avatar", "bio", "phone"),
            },
        ),
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
