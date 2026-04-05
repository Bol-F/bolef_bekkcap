from django.contrib.auth import get_user_model
<<<<<<< HEAD
from django.core.validators import MaxValueValidator, MinValueValidator
=======
from django.core.validators import MinValueValidator, MaxValueValidator
>>>>>>> master
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
            models.Index(fields=["owner", "-created_at"]),
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

    # ✅ Location (Variant B)
    # latitude:  -90..90
    # longitude: -180..180
    # Using DecimalField for stable precision (good for weather APIs).
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Latitude in degrees (-90..90)",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Longitude in degrees (-180..180)",
    )
    location_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Human-readable location (optional)",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["farm", "name"], name="uniq_field_name_per_farm")
        ]
        indexes = [models.Index(fields=["farm"])]

    def __str__(self):
        return f"{self.name} - {self.farm.name}"


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
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default="good")

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
            models.Index(fields=["farm", "-date"]),
            models.Index(fields=["activity_type"]),
        ]

    def __str__(self):
        return f"{self.activity_type} on {self.date} ({self.farm.name})"


class YieldRecord(models.Model):
    """
    Main ML-ready table.
    One row = one training / prediction record.
    This matches the agricultural dataset structure much better than putting
    everything directly inside Farm or Crop.
    """

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


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="profiles/", null=True, blank=True)
    bio = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"Profile of {getattr(self.user, 'username', self.user_id)}"


class EmailOTP(models.Model):
    """
    One-time code for email verification / password reset.
    Stores only hash of the code (sha256), not the raw code.
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "VERIFY_EMAIL", "VERIFY_EMAIL"
        RESET_PASSWORD = "RESET_PASSWORD", "RESET_PASSWORD"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_otps")
    email = models.EmailField(db_index=True)
<<<<<<< HEAD

    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        default=Purpose.VERIFY_EMAIL,
        db_index=True,
    )

    code_hash = models.CharField(max_length=64)  # sha256 hex = 64 chars
=======
    code_hash = models.CharField(max_length=64)
>>>>>>> master
    expires_at = models.DateTimeField()
    attempts_left = models.PositiveSmallIntegerField(default=5)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "purpose", "used", "-created_at"]),
            models.Index(fields=["user", "purpose", "-created_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def __str__(self):
<<<<<<< HEAD
        return f"OTP({self.email}) purpose={self.purpose} used={self.used} exp={self.expires_at}"
=======
        return f"OTP({self.email}) used={self.used} exp={self.expires_at}"
>>>>>>> master
