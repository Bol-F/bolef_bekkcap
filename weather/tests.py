from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from farm.models import Farm, Field
from .models import IrrigationRecommendation, WeatherSnapshot

User = get_user_model()


class WeatherApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="weatheruser",
            email="weather@example.com",
            password="Testpass123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.farm = Farm.objects.create(
            owner=self.user,
            name="Weather Farm",
            size_hectares="90.00",
            polygon=[
                [69.2400, 41.2990],
                [69.2700, 41.2990],
                [69.2700, 41.3200],
                [69.2400, 41.3200],
                [69.2400, 41.2990],
            ],
        )

        self.field = Field.objects.create(
            farm=self.farm,
            name="Weather Field",
            area="10.00",
            soil_type="loamy",
            polygon=[
                [69.2450, 41.3020],
                [69.2550, 41.3020],
                [69.2550, 41.3090],
                [69.2450, 41.3090],
                [69.2450, 41.3020],
            ],
        )

        self.snapshot = WeatherSnapshot.objects.create(
            field=self.field,
            source="open-meteo",
            latitude=Decimal("41.305000"),
            longitude=Decimal("69.250000"),
            forecast_date="2026-04-15",
            rain_next_24h_mm=Decimal("2.50"),
            rain_next_72h_mm=Decimal("8.00"),
            rain_next_7d_mm=Decimal("18.00"),
            max_rain_probability_24h=Decimal("45.00"),
            evapotranspiration_24h=Decimal("4.20"),
            avg_temperature_24h=Decimal("22.50"),
            raw_data={"hourly": {}},
        )

        self.recommendation = IrrigationRecommendation.objects.create(
            field=self.field,
            weather_snapshot=self.snapshot,
            status="water_later",
            severity="medium",
            recommendation="Plan light irrigation later.",
            reason="Low rain and moderate evapotranspiration.",
            recommended_time="evening",
            rain_next_24h_mm=Decimal("2.50"),
            rain_next_72h_mm=Decimal("8.00"),
            rain_next_7d_mm=Decimal("18.00"),
            evapotranspiration_24h=Decimal("4.20"),
            evidence={"weather": {"rain_next_24h_mm": 2.5}},
        )

    def test_health(self):
        response = self.client.get("/api/v1/weather/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["service"], "weather")

    @patch("weather.views.ensure_fresh_weather_snapshot")
    def test_forecast_endpoint(self, mock_snapshot):
        mock_snapshot.return_value = self.snapshot

        response = self.client.post(
            f"/api/v1/weather/fields/{self.field.id}/forecast/",
            {"force_refresh": False, "max_age_hours": 18},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["field_id"], self.field.id)

    def test_latest_weather_endpoint(self):
        response = self.client.get(f"/api/v1/weather/fields/{self.field.id}/latest/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["snapshot"]["id"], self.snapshot.id)

    @patch("weather.views.ensure_fresh_irrigation_recommendation")
    def test_irrigation_plan_endpoint(self, mock_advice):
        mock_advice.return_value = (self.snapshot, self.recommendation)

        response = self.client.post(
            f"/api/v1/weather/fields/{self.field.id}/irrigation-plan/",
            {"force_refresh": False, "max_age_hours": 18},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["recommendation"]["status"], "water_later")

    def test_latest_irrigation_plan_endpoint(self):
        response = self.client.get(
            f"/api/v1/weather/fields/{self.field.id}/irrigation-plan/latest/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["recommendation"]["id"], self.recommendation.id)

    @patch("weather.views.ensure_fresh_irrigation_recommendation")
    def test_combined_advice_endpoint(self, mock_advice):
        mock_advice.return_value = (self.snapshot, self.recommendation)

        response = self.client.post(
            f"/api/v1/weather/fields/{self.field.id}/advice/",
            {"force_refresh": False, "max_age_hours": 18},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("snapshot", response.data)
        self.assertIn("recommendation", response.data)
