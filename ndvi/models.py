from django.db import models


def classify_ndvi(value: float) -> str:
    if value < 0.2:
        return "bare"
    if value < 0.4:
        return "poor"
    if value < 0.6:
        return "moderate"
    return "healthy"


class NDVIRecord(models.Model):
    SOURCE_CHOICES = [
        ("synthetic", "Synthetic"),
        ("huggingface", "HuggingFace"),
        ("sentinel_api", "Sentinel API"),
    ]

    STATUS_CHOICES = [
        ("bare", "Bare / no vegetation"),
        ("poor", "Poor"),
        ("moderate", "Moderate"),
        ("healthy", "Healthy"),
    ]

    field = models.ForeignKey(
        "farm.Field",
        on_delete=models.CASCADE,
        related_name="ndvi_records",
    )
    date = models.DateField()

    ndvi_mean = models.FloatField()
    ndvi_min = models.FloatField(null=True, blank=True)
    ndvi_max = models.FloatField(null=True, blank=True)
    ndvi_std = models.FloatField(null=True, blank=True)

    evi_mean = models.FloatField(null=True, blank=True)
    tcg_mean = models.FloatField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="synthetic",
    )
    cloud_coverage = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["field", "date"], name="uniq_ndvi_record_per_field_date"
            )
        ]
        indexes = [
            models.Index(fields=["field", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self) -> str:
        field_name = getattr(self.field, "name", self.field_id)
        return f"{field_name} | {self.date} | {self.ndvi_mean:.3f}"

    def save(self, *args, **kwargs):
        self.status = classify_ndvi(float(self.ndvi_mean))
        super().save(*args, **kwargs)
