from django.core.management.base import BaseCommand

from farm.models import Field
from weather.services import ensure_fresh_irrigation_recommendation


class Command(BaseCommand):
    help = "Refresh weather snapshots and irrigation recommendations for fields with location."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-refresh",
            action="store_true",
            help="Force refresh even if cached weather is still fresh.",
        )
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=18,
            help="Refresh if weather snapshot is older than this number of hours.",
        )

    def handle(self, *args, **options):
        force_refresh = options["force_refresh"]
        max_age_hours = options["max_age_hours"]

        fields = Field.objects.select_related("farm").all()
        processed = 0
        failed = 0

        for field in fields:
            if not field.has_location:
                continue

            try:
                ensure_fresh_irrigation_recommendation(
                    field=field,
                    max_age_hours=max_age_hours,
                    force_refresh=force_refresh,
                )
                processed += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Failed for field {field.id} ({field.name}): {exc}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Weather refresh complete. Processed: {processed}, Failed: {failed}"
            )
        )
