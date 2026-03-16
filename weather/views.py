from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from farm.models import Field
from .services import fetch_open_meteo_forecast


class FieldWeatherForecastView(APIView):
    """
    GET /api/v1/weather/forecast/?field_id=1&days=3

    - checks ownership: field.farm.owner == request.user
    - requires Field.latitude & Field.longitude
    - returns Open-Meteo raw JSON + field info
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        field_id = request.query_params.get("field_id")
        if not field_id:
            return Response({"detail": "field_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            days = int(request.query_params.get("days", 3))
        except Exception:
            return Response({"detail": "days must be integer"}, status=status.HTTP_400_BAD_REQUEST)

        if days < 1 or days > 16:
            return Response({"detail": "days must be between 1 and 16"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            field = Field.objects.select_related("farm").get(id=field_id, farm__owner=request.user)
        except Field.DoesNotExist:
            return Response({"detail": "Field not found"}, status=status.HTTP_404_NOT_FOUND)

        if field.latitude is None or field.longitude is None:
            return Response(
                {"detail": "Field latitude/longitude not set. Update the field first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lat = float(field.latitude)
        lon = float(field.longitude)

        try:
            data, from_cache = fetch_open_meteo_forecast(lat=lat, lon=lon, days=days, timezone="auto")
        except Exception as e:
            return Response(
                {"detail": "Weather provider error", "error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "field": {
                    "id": field.id,
                    "name": field.name,
                    "latitude": lat,
                    "longitude": lon,
                    "location_text": field.location_text,
                },
                "source": "open-meteo",
                "from_cache": from_cache,
                "data": data,
            },
            status=status.HTTP_200_OK,
        )
