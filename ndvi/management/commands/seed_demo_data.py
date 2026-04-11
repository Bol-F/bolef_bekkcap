from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from farm.models import Farm, Field
from ndvi.models import NDVIRecord, classify_ndvi
from ndvi.services.dataset_loader import get_ndvi_data

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo user, farm, field, and populate NDVI records."

    def handle(self, *args, **options):
        polygon = [
            [69.2400, 41.2990],
            [69.2500, 41.2990],
            [69.2500, 41.3050],
            [69.2400, 41.3050],
            [69.2400, 41.2990],
        ]

        user, _ = User.objects.get_or_create(
            username="demo_farmer",
            defaults={
                "email": "demo@example.com",
                "is_active": True,
            },
        )

        farm, _ = Farm.objects.get_or_create(
            owner=user,
            name="Demo Farm Tashkent",
            defaults={
                "location": "Tashkent",
                "size_hectares": 10,
            },
        )

        field, _ = Field.objects.get_or_create(
            farm=farm,
            name="Demo Field Tashkent",
            defaults={
                "area": 2.5,
                "soil_type": "loamy",
                "polygon": polygon,
            },
        )

        center_lat = float(field.latitude) if field.latitude is not None else None
        center_lon = float(field.longitude) if field.longitude is not None else None

        raw = get_ndvi_data(
            center_lat=center_lat,
            center_lon=center_lon,
            date_from="2024-03-01",
            date_to="2024-10-01",
            polygon=field.polygon,
        )

        created_count = 0
        for r in raw:
            _, was_created = NDVIRecord.objects.get_or_create(
                field=field,
                date=r["date"],
                defaults={
                    "ndvi_mean": r["ndvi_mean"],
                    "ndvi_min": r.get("ndvi_min"),
                    "ndvi_max": r.get("ndvi_max"),
                    "ndvi_std": r.get("ndvi_std"),
                    "evi_mean": r.get("evi_mean"),
                    "tcg_mean": r.get("tcg_mean"),
                    "cloud_coverage": r.get("cloud_coverage"),
                    "status": classify_ndvi(r["ndvi_mean"]),
                    "source": r.get("source", "synthetic"),
                },
            )
            if was_created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Farm ready: {farm.name} | Field ready: {field.name} | new NDVI records: {created_count}"
            )
        )
