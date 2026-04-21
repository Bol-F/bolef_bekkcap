from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from farm.models import Field
from ndvi.models import NDVIRecord, classify_ndvi
from ndvi.services.dataset_loader import get_ndvi_data


def field_center(field):
    lat = getattr(field, "latitude", None)
    lon = getattr(field, "longitude", None)

    if lat is not None and lon is not None:
        return float(lat), float(lon)

    polygon = getattr(field, "polygon", None)
    if polygon:
        points = polygon[:-1] if polygon[0] == polygon[-1] else polygon
        center_lat = sum(p[1] for p in points) / len(points)
        center_lon = sum(p[0] for p in points) / len(points)
        return float(center_lat), float(center_lon)

    return None, None


def bbox_polygon(lat: float, lon: float, padding: float = 0.01):
    min_lon = lon - padding
    max_lon = lon + padding
    min_lat = lat - padding
    max_lat = lat + padding

    return [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]


def field_polygon_for_satellite(field):
    polygon = getattr(field, "polygon", None)
    if polygon:
        normalized = [list(p) for p in polygon]
        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])
        return normalized

    lat, lon = field_center(field)
    if lat is not None and lon is not None:
        return bbox_polygon(lat, lon)

    return None


class Command(BaseCommand):
    help = "Fetch NDVI records for all fields or all fields in one farm."

    def add_arguments(self, parser):
        parser.add_argument(
            "--farm-id",
            type=int,
            default=None,
            help="Only refresh fields from one farm.",
        )
        parser.add_argument(
            "--date-from",
            type=str,
            default=None,
            help="Start date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--date-to",
            type=str,
            default=None,
            help="End date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Delete existing NDVI records in the range before fetching again.",
        )

    def handle(self, *args, **options):
        d_to = options["date_to"] or str(date.today())
        d_from = options["date_from"] or str(date.today() - timedelta(days=180))
        farm_id = options["farm_id"]
        force_refresh = options["force_refresh"]

        fields = Field.objects.select_related("farm").all()
        if farm_id:
            fields = fields.filter(farm_id=farm_id)

        processed = 0
        failed = 0
        total_new = 0
        total_skipped = 0

        for field in fields:
            center_lat, center_lon = field_center(field)
            polygon = field_polygon_for_satellite(field)

            if center_lat is None or center_lon is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping field {field.id} ({field.name}): no location"
                    )
                )
                continue

            if force_refresh:
                NDVIRecord.objects.filter(
                    field=field,
                    date__gte=d_from,
                    date__lte=d_to,
                ).delete()

            existing_dates = set(
                str(d)
                for d in NDVIRecord.objects.filter(
                    field=field,
                    date__gte=d_from,
                    date__lte=d_to,
                ).values_list("date", flat=True)
            )

            try:
                raw = get_ndvi_data(
                    center_lat=center_lat,
                    center_lon=center_lon,
                    date_from=d_from,
                    date_to=d_to,
                    polygon=polygon,
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Failed for field {field.id} ({field.name}): {exc}"
                    )
                )
                continue

            to_create = []
            skipped_existing = 0

            for record in raw:
                record_date = str(record["date"])

                if record_date in existing_dates:
                    skipped_existing += 1
                    continue

                to_create.append(
                    NDVIRecord(
                        field=field,
                        date=record["date"],
                        ndvi_mean=record["ndvi_mean"],
                        ndvi_min=record.get("ndvi_min"),
                        ndvi_max=record.get("ndvi_max"),
                        ndvi_std=record.get("ndvi_std"),
                        evi_mean=record.get("evi_mean"),
                        tcg_mean=record.get("tcg_mean"),
                        cloud_coverage=record.get("cloud_coverage"),
                        status=classify_ndvi(record["ndvi_mean"]),
                        source=record.get(
                            "source",
                            getattr(settings, "NDVI_DATA_SOURCE", "synthetic"),
                        ),
                    )
                )
                existing_dates.add(record_date)

            created = NDVIRecord.objects.bulk_create(to_create, ignore_conflicts=True)

            processed += 1
            total_new += len(created)
            total_skipped += skipped_existing

            self.stdout.write(
                self.style.SUCCESS(
                    f"Field {field.id} ({field.name}): new={len(created)}, skipped={skipped_existing}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"NDVI refresh complete. Processed={processed}, Failed={failed}, New={total_new}, Skipped={total_skipped}"
            )
        )