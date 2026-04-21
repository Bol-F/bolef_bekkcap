from django.db import models


class WeatherSnapshot(models.Model):
    field = models.ForeignKey(
        "farm.Field",
        on_delete=models.CASCADE,
        related_name="weather_snapshots",
    )

    source = models.CharField(max_length=50, default="open-meteo")

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    forecast_date = models.DateField()

    rain_next_24h_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rain_next_72h_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rain_next_7d_mm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_rain_probability_24h = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    evapotranspiration_24h = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    avg_temperature_24h = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["field", "-created_at"]),
            models.Index(fields=["forecast_date"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        return f"Weather for {self.field.name} on {self.forecast_date}"


class IrrigationRecommendation(models.Model):
    STATUS_CHOICES = [
        ("water_now", "Water Now"),
        ("water_later", "Water Later"),
        ("skip_rain_expected", "Skip: Rain Expected"),
        ("skip_soil_wet", "Skip: Soil Already Wet"),
        ("drainage_warning", "Drainage Warning"),
        ("watch", "Watch"),
        ("unknown", "Unknown"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    field = models.ForeignKey(
        "farm.Field",
        on_delete=models.CASCADE,
        related_name="irrigation_recommendations",
    )
    weather_snapshot = models.ForeignKey(
        WeatherSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="irrigation_recommendations",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="unknown",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="low",
    )

    recommendation = models.TextField()
    reason = models.TextField(blank=True)
    recommended_time = models.CharField(
        max_length=100,
        blank=True,
        help_text="Example: early_morning, evening, after_rain, none",
    )

    rain_next_24h_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rain_next_72h_mm = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rain_next_7d_mm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    evapotranspiration_24h = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )

    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["field", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return f"{self.field.name} | {self.status} | {self.created_at.date()}"
