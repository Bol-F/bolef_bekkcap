from django.contrib import admin

from .models import SoilMeasurement


@admin.register(SoilMeasurement)
class SoilMeasurementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "field",
        "field_farm",
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
    search_fields = (
        "field__name",
        "field__farm__name",
        "field__farm__owner__username",
        "notes",
    )
    list_filter = ("soil_type", "sample_date", "created_at")
    ordering = ("-sample_date", "-created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("field", "yield_record")
    list_select_related = ("field", "field__farm", "yield_record", "yield_record__farm")

    def field_farm(self, obj):
        return obj.field.farm.name

    field_farm.short_description = "Farm"
