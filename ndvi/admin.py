from django.contrib import admin

from .models import NDVIRecord


@admin.register(NDVIRecord)
class NDVIRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "field",
        "field_farm",
        "date",
        "ndvi_mean",
        "status",
        "source",
        "cloud_coverage",
        "created_at",
    )
    list_filter = (
        "status",
        "source",
        "date",
        "field__farm",
    )
    search_fields = (
        "field__name",
        "field__farm__name",
        "field__farm__owner__username",
    )
    readonly_fields = (
        "status",
        "created_at",
    )
    autocomplete_fields = ("field",)
    ordering = ("-date", "-created_at")
    list_select_related = ("field", "field__farm", "field__farm__owner")

    def field_farm(self, obj):
        return obj.field.farm.name

    field_farm.short_description = "Farm"
