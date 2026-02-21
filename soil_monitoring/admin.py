"""
Django Admin Configuration for Soil Monitoring
Copy-paste safe (fixes SafeString formatting issue)
"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import FieldSoilProfile, SensorReading, Recommendation, Notification


# -----------------------------
# FieldSoilProfile
# -----------------------------
@admin.register(FieldSoilProfile)
class FieldSoilProfileAdmin(admin.ModelAdmin):
    list_display = (
        "field",
        "fc_vwc_display",
        "pwp_vwc_display",
        "mad_display",
        "ph_range",
        "ec_max_display",
        "temp_range",
        "updated_at",
    )
    list_filter = ("updated_at",)
    search_fields = ("field__name",)
    readonly_fields = ("updated_at",)

    fieldsets = (
        ("Поле", {"fields": ("field",)}),
        (
            "Параметры влажности (VWC)",
            {
                "fields": ("fc_vwc", "pwp_vwc", "mad"),
                "description": "Field Capacity, Permanent Wilting Point, Management Allowed Depletion",
            },
        ),
        ("Параметры pH", {"fields": ("ph_min", "ph_max")}),
        ("Параметры засоленности", {"fields": ("ec_max_ds_m",)}),
        ("Температурные пороги", {"fields": ("temp_min_c", "temp_max_c")}),
        ("Метаданные", {"fields": ("updated_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="FC (VWC)")
    def fc_vwc_display(self, obj):
        return f"{obj.fc_vwc:.2f} ({obj.fc_vwc * 100:.0f}%)"

    @admin.display(description="PWP (VWC)")
    def pwp_vwc_display(self, obj):
        return f"{obj.pwp_vwc:.2f} ({obj.pwp_vwc * 100:.0f}%)"

    @admin.display(description="MAD")
    def mad_display(self, obj):
        return f"{obj.mad:.2f} ({obj.mad * 100:.0f}%)"

    @admin.display(description="pH Range")
    def ph_range(self, obj):
        return f"{obj.ph_min:.1f} - {obj.ph_max:.1f}"

    @admin.display(description="EC Max")
    def ec_max_display(self, obj):
        return f"{obj.ec_max_ds_m:.1f} dS/m"

    @admin.display(description="Temp Range")
    def temp_range(self, obj):
        return f"{obj.temp_min_c:.0f}°C - {obj.temp_max_c:.0f}°C"


# -----------------------------
# SensorReading
# -----------------------------
@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = (
        "field",
        "ts",
        "moisture_display",
        "ph",
        "ec_display",
        "temp_display",
        "depth_cm",
        "source",
        "health_indicator",
    )
    list_filter = ("field", "source", "ts")
    search_fields = ("field__name",)
    readonly_fields = ("created_at",)
    date_hierarchy = "ts"

    # speed up admin list (health_indicator uses soil_profile)
    list_select_related = ("field", "field__farm", "field__soil_profile")

    fieldsets = (
        ("Основная информация", {"fields": ("field", "ts", "source", "depth_cm")}),
        ("Показания датчиков", {"fields": ("moisture_vwc", "ph", "ec_ds_m", "soil_temp_c")}),
        ("Метаданные", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Влажность (VWC)")
    def moisture_display(self, obj):
        """
        IMPORTANT: do numeric formatting before format_html (avoid SafeString {:.2f} crash)
        """
        if obj.moisture_vwc is None:
            return "-"

        pct = obj.moisture_vwc * 100

        # Default style
        color = "gray"
        icon = "•"

        try:
            profile = obj.field.soil_profile
            threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)

            if obj.moisture_vwc < profile.pwp_vwc:
                color = "red"
                icon = "🚨"
            elif obj.moisture_vwc < threshold:
                color = "orange"
                icon = "⚠️"
            elif obj.moisture_vwc > profile.fc_vwc * 1.15:
                color = "blue"
                icon = "💧"
            else:
                color = "green"
                icon = "✓"
        except Exception:
            pass

        # Format numbers as strings BEFORE format_html
        text = f"{icon} {obj.moisture_vwc:.2f} ({pct:.0f}%)"
        return format_html('<span style="color: {};">{}</span>', color, text)

    @admin.display(description="EC")
    def ec_display(self, obj):
        if obj.ec_ds_m is None:
            return "-"
        return f"{obj.ec_ds_m:.2f} dS/m"

    @admin.display(description="Температура")
    def temp_display(self, obj):
        if obj.soil_temp_c is None:
            return "-"
        return f"{obj.soil_temp_c:.1f}°C"

    @admin.display(description="Статус")
    def health_indicator(self, obj):
        try:
            profile = obj.field.soil_profile
            issues = []

            # Moisture
            if obj.moisture_vwc is not None:
                threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)
                if obj.moisture_vwc < profile.pwp_vwc:
                    issues.append("💧 Critical")
                elif obj.moisture_vwc < threshold:
                    issues.append("💧 Low")

            # pH
            if obj.ph is not None:
                if obj.ph < profile.ph_min or obj.ph > profile.ph_max:
                    issues.append("🔬 pH")

            # EC
            if obj.ec_ds_m is not None and obj.ec_ds_m > profile.ec_max_ds_m:
                issues.append("⚡ Saline")

            # Temp
            if obj.soil_temp_c is not None:
                if obj.soil_temp_c < profile.temp_min_c or obj.soil_temp_c > profile.temp_max_c:
                    issues.append("🌡️ Temp")

            if issues:
                return format_html('<span style="color: red;">{}</span>', ", ".join(issues))
            return format_html('<span style="color: green;">✓ OK</span>')
        except Exception:
            return "-"


# -----------------------------
# Recommendation
# -----------------------------
@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "field",
        "category_badge",
        "severity_badge",
        "title_short",
        "created_at",
        "is_active",
        "age",
    )
    list_filter = ("category", "severity", "is_active", "created_at")
    search_fields = ("field__name", "title", "message")
    readonly_fields = ("created_at", "evidence_display")
    date_hierarchy = "created_at"
    actions = ("deactivate_recommendations",)

    list_select_related = ("field", "field__farm")

    fieldsets = (
        ("Основная информация", {"fields": ("field", "category", "severity", "is_active")}),
        ("Содержание", {"fields": ("title", "message")}),
        ("Доказательства", {"fields": ("evidence_display",), "classes": ("collapse",)}),
        ("Метаданные", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Категория")
    def category_badge(self, obj):
        colors = {
            "IRRIGATION": "blue",
            "SOIL_PH": "purple",
            "SOIL_EC": "orange",
            "SOIL_TEMP": "red",
        }
        color = colors.get(obj.category, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_category_display(),
        )

    @admin.display(description="Серьезность")
    def severity_badge(self, obj):
        colors = {
            "LOW": "#90EE90",
            "MED": "#FFD700",
            "HIGH": "#FF6347",
        }
        icons = {"LOW": "ℹ️", "MED": "⚠️", "HIGH": "🚨"}
        label = f"{icons.get(obj.severity, '?')} {obj.get_severity_display()}"
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.severity, "gray"),
            label,
        )

    @admin.display(description="Заголовок")
    def title_short(self, obj):
        return (obj.title[:50] + "...") if len(obj.title) > 50 else obj.title

    @admin.display(description="Возраст")
    def age(self, obj):
        delta = timezone.now() - obj.created_at
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return f"{int(delta.total_seconds() / 60)} мин"
        if hours < 24:
            return f"{int(hours)} ч"
        return f"{int(hours / 24)} дн"

    @admin.display(description="Доказательства (JSON)")
    def evidence_display(self, obj):
        import json
        return format_html("<pre>{}</pre>", json.dumps(obj.evidence, indent=2, ensure_ascii=False))

    @admin.action(description="Деактивировать выбранные")
    def deactivate_recommendations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} рекомендаций деактивировано")


# -----------------------------
# Notification
# -----------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "recommendation_short",
        "channel",
        "status_badge",
        "created_at",
        "sent_at",
    )
    list_filter = ("channel", "status", "created_at")
    search_fields = ("user__username", "recommendation__title")
    readonly_fields = ("created_at", "sent_at", "payload_display")
    date_hierarchy = "created_at"

    list_select_related = ("user", "recommendation", "recommendation__field")

    fieldsets = (
        ("Основная информация", {"fields": ("user", "recommendation", "channel", "status")}),
        ("Данные", {"fields": ("payload_display", "error"), "classes": ("collapse",)}),
        ("Временные метки", {"fields": ("created_at", "sent_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Рекомендация")
    def recommendation_short(self, obj):
        title = obj.recommendation.title if obj.recommendation_id else "-"
        return (title[:40] + "...") if title and len(title) > 40 else title

    @admin.display(description="Статус")
    def status_badge(self, obj):
        colors = {"PENDING": "orange", "SENT": "green", "FAILED": "red"}
        return format_html('<span style="color: {};">{}</span>', colors.get(obj.status, "gray"), obj.get_status_display())

    @admin.display(description="Payload (JSON)")
    def payload_display(self, obj):
        import json
        return format_html("<pre>{}</pre>", json.dumps(obj.payload, indent=2, ensure_ascii=False))