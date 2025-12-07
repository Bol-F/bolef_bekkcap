from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Farm(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="farms")
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True)
    size_hectares = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Farm size in hectares",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class Field(models.Model):
    SOIL_CHOICES = [
        ("loam", "Loam"),
        ("sand", "Sandy"),
        ("clay", "Clay"),
        ("other", "Other"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="fields")
    name = models.CharField(max_length=100)
    area = models.DecimalField(
        max_digits=6, decimal_places=2, help_text="Field area in hectares"
    )
    soil_type = models.CharField(max_length=20, choices=SOIL_CHOICES, default="loam")

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

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class Animal(models.Model):
    HEALTH_CHOICES = [
        ("good", "Good"),
        ("sick", "Sick"),
        ("critical", "Critical"),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="animals")
    species = models.CharField(max_length=50)  # e.g. Cow, Sheep, Chicken
    tag_id = models.CharField(
        max_length=50, unique=True, help_text="Unique ID for the animal (ear tag, etc.)"
    )
    birth_date = models.DateField(null=True, blank=True)
    health_status = models.CharField(
        max_length=20, choices=HEALTH_CHOICES, default="good"
    )

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

    # Optional links (not required, can be NULL)
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

    def __str__(self):
        return f"{self.activity_type} on {self.date} ({self.farm.name})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="profiles/", null=True, blank=True)
    bio = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"
