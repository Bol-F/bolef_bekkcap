from __future__ import annotations

import math

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

User = get_user_model()


SOIL_CHOICES = [
    ("loamy", "Loamy"),
    ("sandy", "Sandy"),
    ("clay", "Clay"),
    ("silty", "Silty"),
    ("peaty", "Peaty"),
    ("other", "Other"),
]

SEASON_CHOICES = [
    ("kharif", "Kharif"),
    ("rabi", "Rabi"),
    ("zaid", "Zaid"),
    ("other", "Other"),
]

IRRIGATION_CHOICES = [
    ("drip", "Drip"),
    ("sprinkler", "Sprinkler"),
    ("manual", "Manual"),
    ("flood", "Flood"),
    ("rainfed", "Rain-fed"),
    ("other", "Other"),
]


class Farm(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="farms")
    name = models.CharField(max_length=100)
    farm_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Optional external farm ID like F001",
    )
    location = models.CharField(max_length=200, blank=True)
    size_hectares = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Farm size in hectares",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["farm_code"]),
        ]

    def __str__(self):
        return f"{self.name} ({getattr(self.owner, 'username', self.owner_id)})"


class Field(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="fields")
    name = models.CharField(max_length=100)
    area = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Field area in hectares",
    )
    soil_type = models.CharField(max_length=20, choices=SOIL_CHOICES, default="loamy")

    # Simple map support (legacy-compatible)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Field center latitude",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Field center longitude",
    )

    # Better NDVI / map support
    polygon = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional polygon as [[lon, lat], [lon, lat], ...]. Auto-closed on save.",
    )
    bbox_min_lon = models.FloatField(null=True, blank=True, editable=False)
    bbox_max_lon = models.FloatField(null=True, blank=True, editable=False)
    bbox_min_lat = models.FloatField(null=True, blank=True, editable=False)
    bbox_max_lat = models.FloatField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["farm", "name"],
                name="uniq_field_name_per_farm",
            )
        ]
        indexes = [
            models.Index(fields=["farm"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.farm.name}"

    def clean(self):
        super().clean()

        if (self.latitude is None) ^ (self.longitude is None):
            raise ValidationError(
                "Set both latitude and longitude, or leave both empty."
            )

        if self.polygon:
            if not isinstance(self.polygon, list) or len(self.polygon) < 4:
                raise ValidationError("Polygon must have at least 4 coordinate pairs.")

            for pt in self.polygon:
                if not isinstance(pt, list) or len(pt) != 2:
                    raise ValidationError(
                        f"Each polygon point must be [lon, lat]. Got: {pt}"
                    )

                lon, lat = pt
                if not (-180 <= lon <= 180):
                    raise ValidationError(f"Polygon longitude out of range: {lon}")
                if not (-90 <= lat <= 90):
                    raise ValidationError(f"Polygon latitude out of range: {lat}")

    def save(self, *args, **kwargs):
        self._normalize_polygon()
        if self.polygon:
            self._sync_spatial_fields_from_polygon()
        self.full_clean()
        super().save(*args, **kwargs)

    def _normalize_polygon(self):
        if not self.polygon or not isinstance(self.polygon, list):
            return

        if self.polygon[0] != self.polygon[-1]:
            self.polygon.append(self.polygon[0])

    def _unique_polygon_points(self):
        if not self.polygon:
            return []
        if len(self.polygon) >= 2 and self.polygon[0] == self.polygon[-1]:
            return self.polygon[:-1]
        return self.polygon

    def _sync_spatial_fields_from_polygon(self):
        points = self._unique_polygon_points()
        if not points:
            return

        lons = [p[0] for p in points]
        lats = [p[1] for p in points]

        center_lon = sum(lons) / len(lons)
        center_lat = sum(lats) / len(lats)

        self.longitude = round(center_lon, 6)
        self.latitude = round(center_lat, 6)

        self.bbox_min_lon = min(lons)
        self.bbox_max_lon = max(lons)
        self.bbox_min_lat = min(lats)
        self.bbox_max_lat = max(lats)

    @property
    def has_location(self) -> bool:
        return bool(
            (self.latitude is not None and self.longitude is not None) or self.polygon
        )

    @property
    def polygon_area_approx_ha(self) -> float | None:
        points = self._unique_polygon_points()
        if len(points) < 3:
            return None

        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        area = abs(area) / 2.0

        center_lat = float(self.latitude) if self.latitude is not None else 0.0
        lat_rad = math.radians(center_lat)
        meters_per_deg_lon = 111320 * math.cos(lat_rad)
        meters_per_deg_lat = 110540
        area_m2 = area * meters_per_deg_lon * meters_per_deg_lat
        return round(area_m2 / 10_000, 2)


class Crop(models.Model):
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("growing", "Growing"),
        ("harvested", "Harvested"),
    ]

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="crops")
    name = models.CharField(max_length=100)
    plant_date = models.DateField(null=True, blank=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["field", "status"])]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class Animal(models.Model):
    HEALTH_CHOICES = [
        ("good", "Good"),
        ("sick", "Sick"),
        ("critical", "Critical"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="animals")
    species = models.CharField(max_length=50)
    tag_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique ID for the animal (ear tag, etc.)",
    )
    birth_date = models.DateField(null=True, blank=True)
    health_status = models.CharField(
        max_length=20,
        choices=HEALTH_CHOICES,
        default="good",
    )

    class Meta:
        ordering = ["species", "tag_id"]
        indexes = [models.Index(fields=["farm", "health_status"])]

    def __str__(self):
        return f"{self.species} #{self.tag_id}"


class ActivityLog(models.Model):
    ACTIVITY_CHOICES = [
        ("watering", "Watering"),
        ("fertilizing", "Fertilizing"),
        ("feeding", "Feeding"),
        ("harvesting", "Harvesting"),
        ("vet_check", "Vet Check"),
        ("other", "Other"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="activities")
    date = models.DateField()
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    description = models.TextField(blank=True)

    field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    crop = models.ForeignKey(
        Crop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    animal = models.ForeignKey(
        Animal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["farm", "date"]),
            models.Index(fields=["activity_type"]),
        ]

    def __str__(self):
        return f"{self.activity_type} on {self.date} ({self.farm.name})"

    def clean(self):
        super().clean()

        if self.field and self.field.farm_id != self.farm_id:
            raise ValidationError(
                {"field": "Selected field does not belong to the selected farm."}
            )

        if self.crop and self.crop.field.farm_id != self.farm_id:
            raise ValidationError(
                {"crop": "Selected crop does not belong to the selected farm."}
            )

        if self.animal and self.animal.farm_id != self.farm_id:
            raise ValidationError(
                {"animal": "Selected animal does not belong to the selected farm."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class YieldRecord(models.Model):
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="yield_records",
    )
    field = models.ForeignKey(
        Field,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yield_records",
    )

    crop_type = models.CharField(max_length=100)
    season = models.CharField(max_length=20, choices=SEASON_CHOICES)
    irrigation_type = models.CharField(max_length=20, choices=IRRIGATION_CHOICES)
    soil_type = models.CharField(max_length=20, choices=SOIL_CHOICES)

    farm_area_acres = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    fertilizer_used_tons = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    pesticide_used_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    water_usage_cubic_meters = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    actual_yield_tons = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Real yield from dataset or from actual harvest",
    )

    predicted_yield_tons = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="ML predicted yield",
    )

    model_name = models.CharField(max_length=100, blank=True)
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Optional confidence in percent",
    )

    notes = models.TextField(blank=True)
    prediction_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["farm", "crop_type"]),
            models.Index(fields=["season"]),
            models.Index(fields=["irrigation_type"]),
            models.Index(fields=["soil_type"]),
        ]

    def __str__(self):
        return f"{self.farm.name} - {self.crop_type} - {self.season}"

    def clean(self):
        super().clean()
        if self.field and self.field.farm_id != self.farm_id:
            raise ValidationError(
                {"field": "Selected field does not belong to the selected farm."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="profiles/", null=True, blank=True)
    bio = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"Profile of {getattr(self.user, 'username', self.user_id)}"


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_otps")
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts_left = models.PositiveSmallIntegerField(default=5)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "used", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"OTP({self.email}) used={self.used} exp={self.expires_at}"
