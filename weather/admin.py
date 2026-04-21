from django.contrib import admin

from .models import IrrigationRecommendation, WeatherSnapshot


@admin.register(WeatherSnapshot)
class WeatherSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "field",
        "field_farm",
        "forecast_date",
        "rain_next_24h_mm",
        "rain_next_72h_mm",
        "rain_next_7d_mm",
        "evapotranspiration_24h",
        "avg_temperature_24h",
        "created_at",
    )
    search_fields = (
        "field__name",
        "field__farm__name",
        "field__farm__owner__username",
    )
    list_filter = ("source", "forecast_date", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "raw_data")
    autocomplete_fields = ("field",)
    list_select_related = ("field", "field__farm", "field__farm__owner")

    @admin.display(description="Farm")
    def field_farm(self, obj):
        return obj.field.farm.name


@admin.register(IrrigationRecommendation)
class IrrigationRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "field",
        "field_farm",
        "status",
        "severity",
        "recommended_time",
        "rain_next_24h_mm",
        "rain_next_72h_mm",
        "rain_next_7d_mm",
        "created_at",
    )
    search_fields = (
        "field__name",
        "field__farm__name",
        "field__farm__owner__username",
        "recommendation",
        "reason",
    )
    list_filter = ("status", "severity", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "evidence")
    autocomplete_fields = ("field", "weather_snapshot")
    list_select_related = (
        "field",
        "field__farm",
        "field__farm__owner",
        "weather_snapshot",
    )

    @admin.display(description="Farm")
    def field_farm(self, obj):
        return obj.field.farm.name
