from django.contrib import admin

from .models import SoilMeasurement


@admin.register(SoilMeasurement)
class SoilMeasurementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "field",
        "yield_record",
        "soil_type",
        "moisture_percent",
        "ph_level",
        "nitrogen",
        "phosphorus",
        "potassium",
        "sample_date",
        "created_at",
    )
    search_fields = ("field__name", "field__farm__name", "notes")
    list_filter = ("soil_type", "sample_date", "created_at")
    ordering = ("-sample_date", "-created_at")
    readonly_fields = ("created_at",)