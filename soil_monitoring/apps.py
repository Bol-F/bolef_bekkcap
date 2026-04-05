from django.apps import AppConfig


class SoilMonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "soil_monitoring"
    verbose_name = "Soil Monitoring System"

    def ready(self):
        """
        Инициализация при запуске приложения
        Здесь можно добавить signals, scheduled tasks и т.д.
        """
        # Import signals if you create them
        # import soil_monitoring.signals
        pass
