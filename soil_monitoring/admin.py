"""
Django Admin Configuration for Soil Monitoring
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta

from .models import FieldSoilProfile, SensorReading, Recommendation, Notification


@admin.register(FieldSoilProfile)
class FieldSoilProfileAdmin(admin.ModelAdmin):
    list_display = ['field', 'fc_vwc_display', 'pwp_vwc_display', 'mad_display',
                    'ph_range', 'ec_max_display', 'temp_range', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['field__name']
    readonly_fields = ['updated_at']

    fieldsets = (
        ('Поле', {
            'fields': ('field',)
        }),
        ('Параметры влажности (VWC)', {
            'fields': ('fc_vwc', 'pwp_vwc', 'mad'),
            'description': 'Field Capacity, Permanent Wilting Point, Management Allowed Depletion'
        }),
        ('Параметры pH', {
            'fields': ('ph_min', 'ph_max'),
        }),
        ('Параметры засоленности', {
            'fields': ('ec_max_ds_m',),
        }),
        ('Температурные пороги', {
            'fields': ('temp_min_c', 'temp_max_c'),
        }),
        ('Метаданные', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    def fc_vwc_display(self, obj):
        return f"{obj.fc_vwc:.2f} ({obj.fc_vwc * 100:.0f}%)"

    fc_vwc_display.short_description = 'FC (VWC)'

    def pwp_vwc_display(self, obj):
        return f"{obj.pwp_vwc:.2f} ({obj.pwp_vwc * 100:.0f}%)"

    pwp_vwc_display.short_description = 'PWP (VWC)'

    def mad_display(self, obj):
        return f"{obj.mad:.2f} ({obj.mad * 100:.0f}%)"

    mad_display.short_description = 'MAD'

    def ph_range(self, obj):
        return f"{obj.ph_min:.1f} - {obj.ph_max:.1f}"

    ph_range.short_description = 'pH Range'

    def ec_max_display(self, obj):
        return f"{obj.ec_max_ds_m:.1f} dS/m"

    ec_max_display.short_description = 'EC Max'

    def temp_range(self, obj):
        return f"{obj.temp_min_c:.0f}°C - {obj.temp_max_c:.0f}°C"

    temp_range.short_description = 'Temp Range'


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ['field', 'ts', 'moisture_display', 'ph', 'ec_display',
                    'temp_display', 'depth_cm', 'source', 'health_indicator']
    list_filter = ['field', 'source', 'ts']
    search_fields = ['field__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'ts'

    fieldsets = (
        ('Основная информация', {
            'fields': ('field', 'ts', 'source', 'depth_cm')
        }),
        ('Показания датчиков', {
            'fields': ('moisture_vwc', 'ph', 'ec_ds_m', 'soil_temp_c'),
        }),
        ('Метаданные', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def moisture_display(self, obj):
        if obj.moisture_vwc is None:
            return '-'

        try:
            profile = obj.field.soil_profile
            threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)

            if obj.moisture_vwc < profile.pwp_vwc:
                color = 'red'
                icon = '🚨'
            elif obj.moisture_vwc < threshold:
                color = 'orange'
                icon = '⚠️'
            elif obj.moisture_vwc > profile.fc_vwc * 1.1:
                color = 'blue'
                icon = '💧'
            else:
                color = 'green'
                icon = '✓'
        except:
            color = 'gray'
            icon = '?'

        return format_html(
            '<span style="color: {};">{} {:.2f} ({:.0f}%)</span>',
            color, icon, obj.moisture_vwc, obj.moisture_vwc * 100
        )

    moisture_display.short_description = 'Влажность (VWC)'

    def ec_display(self, obj):
        if obj.ec_ds_m is None:
            return '-'
        return f"{obj.ec_ds_m:.2f} dS/m"

    ec_display.short_description = 'EC'

    def temp_display(self, obj):
        if obj.soil_temp_c is None:
            return '-'
        return f"{obj.soil_temp_c:.1f}°C"

    temp_display.short_description = 'Температура'

    def health_indicator(self, obj):
        try:
            profile = obj.field.soil_profile
            issues = []

            # Check moisture
            if obj.moisture_vwc:
                threshold = profile.pwp_vwc + (profile.fc_vwc - profile.pwp_vwc) * (1 - profile.mad)
                if obj.moisture_vwc < profile.pwp_vwc:
                    issues.append('💧 Critical')
                elif obj.moisture_vwc < threshold:
                    issues.append('💧 Low')

            # Check pH
            if obj.ph:
                if obj.ph < profile.ph_min or obj.ph > profile.ph_max:
                    issues.append('🔬 pH')

            # Check EC
            if obj.ec_ds_m and obj.ec_ds_m > profile.ec_max_ds_m:
                issues.append('⚡ Saline')

            # Check temp
            if obj.soil_temp_c:
                if obj.soil_temp_c < profile.temp_min_c or obj.soil_temp_c > profile.temp_max_c:
                    issues.append('🌡️ Temp')

            if issues:
                return format_html('<span style="color: red;">{}</span>', ', '.join(issues))
            return format_html('<span style="color: green;">✓ OK</span>')
        except:
            return '-'

    health_indicator.short_description = 'Статус'


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ['field', 'category_badge', 'severity_badge', 'title_short',
                    'created_at', 'is_active', 'age']
    list_filter = ['category', 'severity', 'is_active', 'created_at']
    search_fields = ['field__name', 'title', 'message']
    readonly_fields = ['created_at', 'evidence_display']
    date_hierarchy = 'created_at'
    actions = ['deactivate_recommendations']

    fieldsets = (
        ('Основная информация', {
            'fields': ('field', 'category', 'severity', 'is_active')
        }),
        ('Содержание', {
            'fields': ('title', 'message'),
        }),
        ('Доказательства', {
            'fields': ('evidence_display',),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def category_badge(self, obj):
        colors = {
            'IRRIGATION': 'blue',
            'SOIL_PH': 'purple',
            'SOIL_EC': 'orange',
            'SOIL_TEMP': 'red',
        }
        color = colors.get(obj.category, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_category_display()
        )

    category_badge.short_description = 'Категория'

    def severity_badge(self, obj):
        colors = {
            'LOW': '#90EE90',
            'MED': '#FFD700',
            'HIGH': '#FF6347',
        }
        icons = {
            'LOW': 'ℹ️',
            'MED': '⚠️',
            'HIGH': '🚨',
        }
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px;">{} {}</span>',
            colors.get(obj.severity, 'gray'),
            icons.get(obj.severity, '?'),
            obj.get_severity_display()
        )

    severity_badge.short_description = 'Серьезность'

    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title

    title_short.short_description = 'Заголовок'

    def age(self, obj):
        delta = timezone.now() - obj.created_at
        hours = delta.total_seconds() / 3600
        if hours < 1:
            return f"{int(delta.total_seconds() / 60)} мин"
        elif hours < 24:
            return f"{int(hours)} ч"
        else:
            return f"{int(hours / 24)} дн"

    age.short_description = 'Возраст'

    def evidence_display(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.evidence, indent=2, ensure_ascii=False))

    evidence_display.short_description = 'Доказательства (JSON)'

    def deactivate_recommendations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} рекомендаций деактивировано')

    deactivate_recommendations.short_description = 'Деактивировать выбранные'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'recommendation_short', 'channel', 'status_badge',
                    'created_at', 'sent_at']
    list_filter = ['channel', 'status', 'created_at']
    search_fields = ['user__username', 'recommendation__title']
    readonly_fields = ['created_at', 'sent_at', 'payload_display']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'recommendation', 'channel', 'status')
        }),
        ('Данные', {
            'fields': ('payload_display', 'error'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('created_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )

    def recommendation_short(self, obj):
        return obj.recommendation.title[:40] + '...' if len(obj.recommendation.title) > 40 else obj.recommendation.title

    recommendation_short.short_description = 'Рекомендация'

    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'SENT': 'green',
            'FAILED': 'red',
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def payload_display(self, obj):
        import json
        return format_html('<pre>{}</pre>', json.dumps(obj.payload, indent=2, ensure_ascii=False))

    payload_display.short_description = 'Payload (JSON)'