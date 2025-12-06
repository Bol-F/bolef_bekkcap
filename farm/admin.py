# farm/admin.py  or farm_api/admin.py (your app name)
from django.contrib import admin
from .models import Farm, Field, Crop, Animal, ActivityLog, UserProfile


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "location", "size_hectares", "created_at")
    list_filter = ("location",)
    search_fields = ("name", "location", "owner__username")


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("name", "farm", "area", "soil_type")
    list_filter = ("soil_type", "farm")
    search_fields = ("name", "farm__name")


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "field", "status", "plant_date", "expected_harvest_date")
    list_filter = ("status", "plant_date")
    search_fields = ("name", "field__name")


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("species", "tag_id", "farm", "health_status", "birth_date")
    list_filter = ("species", "health_status", "farm")
    search_fields = ("species", "tag_id", "farm__name")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("activity_type", "farm", "date", "created_by", "created_at")
    list_filter = ("activity_type", "date", "farm")
    search_fields = ("description", "farm__name", "created_by__username")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bio", "phone")
    search_fields = ("user__username", "phone", "bio")
