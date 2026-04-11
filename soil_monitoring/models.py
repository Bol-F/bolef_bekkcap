from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


SOIL_CHOICES = [
    ("loamy", "Loamy"),
    ("sandy", "Sandy"),
    ("clay", "Clay"),
    ("silty", "Silty"),
    ("peaty", "Peaty"),
    ("other", "Other"),
]


class SoilMeasurement(models.Model):
    field = models.ForeignKey(
        "farm.Field",
        on_delete=models.CASCADE,
        related_name="soil_measurements",
    )
    yield_record = models.ForeignKey(
        "farm.YieldRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="soil_measurements",
    )

    soil_type = models.CharField(max_length=20, choices=SOIL_CHOICES, default="loamy")
    moisture_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    ph_level = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(14)],
    )
    nitrogen = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Nitrogen value",
    )
    phosphorus = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Phosphorus value",
    )
    potassium = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Potassium value",
    )
    temperature_celsius = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    sample_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sample_date", "-created_at"]
        indexes = [
            models.Index(fields=["field", "sample_date"]),
            models.Index(fields=["soil_type"]),
            models.Index(fields=["sample_date"]),
        ]

    def __str__(self):
        return f"SoilMeasurement for {self.field.name} on {self.sample_date}"

    def clean(self):
        super().clean()

        if self.yield_record:
            if self.yield_record.farm_id != self.field.farm_id:
                raise ValidationError(
                    {
                        "yield_record": "Yield record does not belong to the same farm as the selected field."
                    }
                )

            if (
                self.yield_record.field_id
                and self.yield_record.field_id != self.field_id
            ):
                raise ValidationError(
                    {
                        "yield_record": "Yield record does not belong to the selected field."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
