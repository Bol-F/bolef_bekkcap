from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

from farm.models import Field


class FieldSoilProfile(models.Model):
    """
    Профиль/пороги почвы для конкретного поля.
    """

    field = models.OneToOneField(
        Field,
        on_delete=models.CASCADE,
        related_name="soil_profile",
    )

    # Moisture (VWC 0..1)
    fc_vwc = models.FloatField(
        default=0.30,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Field Capacity (VWC 0..1)",
    )
    pwp_vwc = models.FloatField(
        default=0.15,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Permanent Wilting Point (VWC 0..1)",
    )
    mad = models.FloatField(
        default=0.50,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Management Allowed Depletion (0..1)",
    )

    # pH
    ph_min = models.FloatField(
        default=6.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(14.0)],
    )
    ph_max = models.FloatField(
        default=7.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(14.0)],
    )

    # EC (dS/m)
    ec_max_ds_m = models.FloatField(
        default=4.0,
        validators=[MinValueValidator(0.0)],
        help_text="Max EC in dS/m before warnings",
    )

    # Soil temperature
    temp_min_c = models.FloatField(default=10.0)
    temp_max_c = models.FloatField(default=35.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(fc_vwc__gt=F("pwp_vwc")),
                name="soilprofile_fc_gt_pwp",
            ),
            models.CheckConstraint(
                condition=Q(ph_min__lt=F("ph_max")),
                name="soilprofile_ph_min_lt_ph_max",
            ),
            models.CheckConstraint(
                condition=Q(temp_min_c__lt=F("temp_max_c")),
                name="soilprofile_temp_min_lt_temp_max",
            ),
        ]

    def __str__(self) -> str:
        return f"SoilProfile(field={self.field_id})"


class SensorReading(models.Model):
    """
    Показания датчиков по полю.
    """

    class Source(models.TextChoices):
        SENSOR = "sensor", "sensor"
        MANUAL = "manual", "manual"
        TEST = "test", "test"

    field = models.ForeignKey(
        Field, on_delete=models.CASCADE, related_name="soil_readings"
    )
    ts = models.DateTimeField(default=timezone.now, db_index=True)

    moisture_vwc = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    ph = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(14.0)],
    )
    ec_ds_m = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0)],
    )
    soil_temp_c = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-50.0), MaxValueValidator(80.0)],
    )

    depth_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Sensor depth in cm",
    )

    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.SENSOR
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["field", "-ts"]),
            models.Index(fields=["field", "source", "-ts"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(moisture_vwc__isnull=True)
                | (Q(moisture_vwc__gte=0.0) & Q(moisture_vwc__lte=1.0)),
                name="reading_moisture_vwc_0_1_or_null",
            ),
            models.CheckConstraint(
                condition=Q(ph__isnull=True) | (Q(ph__gte=0.0) & Q(ph__lte=14.0)),
                name="reading_ph_0_14_or_null",
            ),
            models.CheckConstraint(
                condition=Q(ec_ds_m__isnull=True) | Q(ec_ds_m__gte=0.0),
                name="reading_ec_nonneg_or_null",
            ),
            models.CheckConstraint(
                condition=Q(soil_temp_c__isnull=True)
                | (Q(soil_temp_c__gte=-50.0) & Q(soil_temp_c__lte=80.0)),
                name="reading_temp_range_or_null",
            ),
        ]

    def __str__(self) -> str:
        return f"Reading(field={self.field_id}, ts={self.ts})"


class Recommendation(models.Model):
    class Severity(models.TextChoices):
        LOW = "LOW", "LOW"
        MED = "MED", "MED"
        HIGH = "HIGH", "HIGH"

    class Category(models.TextChoices):
        IRRIGATION = "IRRIGATION", "IRRIGATION"
        SOIL_PH = "SOIL_PH", "SOIL_PH"
        SOIL_EC = "SOIL_EC", "SOIL_EC"
        SOIL_TEMP = "SOIL_TEMP", "SOIL_TEMP"

    field = models.ForeignKey(
        Field, on_delete=models.CASCADE, related_name="recommendations"
    )
    category = models.CharField(max_length=32, choices=Category.choices)
    severity = models.CharField(max_length=8, choices=Severity.choices)

    title = models.CharField(max_length=120)
    message = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["field", "is_active", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Rec(field={self.field_id}, {self.category}, {self.severity}, active={self.is_active})"


class Notification(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "PENDING"
        SENT = "SENT", "SENT"
        FAILED = "FAILED", "FAILED"

    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "IN_APP"
        WS = "WS", "WS"
        EMAIL = "EMAIL", "EMAIL"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    recommendation = models.ForeignKey(
        Recommendation, on_delete=models.CASCADE, related_name="notifications"
    )

    channel = models.CharField(
        max_length=16, choices=Channel.choices, default=Channel.IN_APP
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )

    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["recommendation", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Notif(user={self.user_id}, rec={self.recommendation_id}, {self.channel}, {self.status})"
