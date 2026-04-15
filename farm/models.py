from __future__ import annotations

import math
from decimal import Decimal

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


def _normalize_polygon(polygon):
    if not polygon:
        return polygon

    if not isinstance(polygon, list):
        raise ValidationError("Polygon must be a list of [lon, lat] points.")

    normalized = []
    for pt in polygon:
        if not isinstance(pt, list) or len(pt) != 2:
            raise ValidationError(f"Each polygon point must be [lon, lat]. Got: {pt}")

        lon, lat = pt
        if not (-180 <= lon <= 180):
            raise ValidationError(f"Polygon longitude out of range: {lon}")
        if not (-90 <= lat <= 90):
            raise ValidationError(f"Polygon latitude out of range: {lat}")

        normalized.append([float(lon), float(lat)])

    if len(normalized) < 4:
        raise ValidationError("Polygon must have at least 4 coordinate pairs.")

    if normalized[0] != normalized[-1]:
        normalized.append(normalized[0])

    return normalized


def _unique_polygon_points(polygon):
    if not polygon:
        return []
    if len(polygon) >= 2 and polygon[0] == polygon[-1]:
        return polygon[:-1]
    return polygon


def _polygon_centroid(polygon):
    points = _unique_polygon_points(polygon)
    if not points:
        return None, None

    lons = [float(p[0]) for p in points]
    lats = [float(p[1]) for p in points]

    center_lon = sum(lons) / len(lons)
    center_lat = sum(lats) / len(lats)
    return center_lat, center_lon


def _polygon_bbox(polygon):
    points = _unique_polygon_points(polygon)
    if not points:
        return None, None, None, None

    lons = [float(p[0]) for p in points]
    lats = [float(p[1]) for p in points]

    return min(lons), max(lons), min(lats), max(lats)


def _polygon_area_approx_ha(polygon, center_lat: float = 0.0):
    points = _unique_polygon_points(polygon)
    if len(points) < 3:
        return None

    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    area = abs(area) / 2.0

    lat_rad = math.radians(center_lat)
    meters_per_deg_lon = 111320 * math.cos(lat_rad)
    meters_per_deg_lat = 110540
    area_m2 = area * meters_per_deg_lon * meters_per_deg_lat
    return round(area_m2 / 10_000, 2)


def _point_in_polygon(point, polygon):
    x, y = point
    points = _unique_polygon_points(polygon)
    inside = False

    n = len(points)
    if n < 3:
        return False

    p1x, p1y = points[0]
    for i in range(1, n + 1):
        p2x, p2y = points[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                else:
                    xinters = p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y

    return inside


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

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Farm center latitude",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Farm center longitude",
    )
    polygon = models.JSONField(
        null=True,
        blank=True,
        help_text="Farm border polygon as [[lon, lat], ...]. Auto-closed on save.",
    )
    bbox_min_lon = models.FloatField(null=True, blank=True, editable=False)
    bbox_max_lon = models.FloatField(null=True, blank=True, editable=False)
    bbox_min_lat = models.FloatField(null=True, blank=True, editable=False)
    bbox_max_lat = models.FloatField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["farm_code"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} ({getattr(self.owner, 'username', self.owner_id)})"

    def clean(self):
        super().clean()

        if (self.latitude is None) ^ (self.longitude is None):
            raise ValidationError("Set both latitude and longitude, or leave both empty.")

        if self.polygon:
            self.polygon = _normalize_polygon(self.polygon)

    def save(self, *args, **kwargs):
        if self.polygon:
            self.polygon = _normalize_polygon(self.polygon)
            self._sync_spatial_fields_from_polygon()

        self.full_clean()
        super().save(*args, **kwargs)

    def _sync_spatial_fields_from_polygon(self):
        center_lat, center_lon = _polygon_centroid(self.polygon)
        min_lon, max_lon, min_lat, max_lat = _polygon_bbox(self.polygon)

        if center_lat is not None and center_lon is not None:
            self.latitude = Decimal(f"{center_lat:.6f}")
            self.longitude = Decimal(f"{center_lon:.6f}")

        self.bbox_min_lon = min_lon
        self.bbox_max_lon = max_lon
        self.bbox_min_lat = min_lat
        self.bbox_max_lat = max_lat

    @property
    def has_location(self) -> bool:
        return bool(
            (self.latitude is not None and self.longitude is not None) or self.polygon
        )

    @property
    def polygon_area_approx_ha(self) -> float | None:
        if not self.polygon:
            return None
        center_lat = float(self.latitude) if self.latitude is not None else 0.0
        return _polygon_area_approx_ha(self.polygon, center_lat=center_lat)


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

    polygon = models.JSONField(
        null=True,
        blank=True,
        help_text="Field polygon as [[lon, lat], ...]. Auto-closed on save.",
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
            raise ValidationError("Set both latitude and longitude, or leave both empty.")

        if self.polygon:
            self.polygon = _normalize_polygon(self.polygon)

        if self.polygon and self.farm and self.farm.polygon:
            farm_polygon = _normalize_polygon(self.farm.polygon)
            field_points = _unique_polygon_points(self.polygon)

            for pt in field_points:
                if not _point_in_polygon(pt, farm_polygon):
                    raise ValidationError(
                        {
                            "polygon": "Field polygon must stay inside the farm polygon."
                        }
                    )

            field_area = self.polygon_area_approx_ha
            farm_area = self.farm.polygon_area_approx_ha

            if field_area is not None and farm_area is not None and field_area > farm_area:
                raise ValidationError(
                    {"polygon": "Field area cannot be bigger than farm area."}
                )

        if self.farm and self.farm.size_hectares is not None and self.area is not None:
            if Decimal(self.area) > Decimal(self.farm.size_hectares):
                raise ValidationError(
                    {"area": "Field area cannot be bigger than farm size."}
                )

    def save(self, *args, **kwargs):
        if self.polygon:
            self.polygon = _normalize_polygon(self.polygon)
            self._sync_spatial_fields_from_polygon()

        self.full_clean()
        super().save(*args, **kwargs)

    def _sync_spatial_fields_from_polygon(self):
        center_lat, center_lon = _polygon_centroid(self.polygon)
        min_lon, max_lon, min_lat, max_lat = _polygon_bbox(self.polygon)

        if center_lat is not None and center_lon is not None:
            self.latitude = Decimal(f"{center_lat:.6f}")
            self.longitude = Decimal(f"{center_lon:.6f}")

        self.bbox_min_lon = min_lon
        self.bbox_max_lon = max_lon
        self.bbox_min_lat = min_lat
        self.bbox_max_lat = max_lat

    @property
    def has_location(self) -> bool:
        return bool(
            (self.latitude is not None and self.longitude is not None) or self.polygon
        )

    @property
    def polygon_area_approx_ha(self) -> float | None:
        if not self.polygon:
            return None
        center_lat = float(self.latitude) if self.latitude is not None else 0.0
        return _polygon_area_approx_ha(self.polygon, center_lat=center_lat)


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