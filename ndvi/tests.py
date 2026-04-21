from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from farm.models import Farm, Field
from .models import NDVIRecord

User = get_user_model()


class NdviApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ndviuser",
            email="ndvi@example.com",
            password="Testpass123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.farm = Farm.objects.create(
            owner=self.user,
            name="NDVI Farm",
            size_hectares="100.00",
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
            name="NDVI Field",
            area="12.00",
            soil_type="loamy",
            polygon=[
                [69.2450, 41.3020],
                [69.2550, 41.3020],
                [69.2550, 41.3090],
                [69.2450, 41.3090],
                [69.2450, 41.3020],
            ],
        )

    def test_health(self):
        response = self.client.get("/api/v1/ndvi/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("ndvi.views.get_ndvi_data")
    def test_fetch_ndvi(self, mock_loader):
        mock_loader.return_value = [
            {
                "date": "2024-03-01",
                "ndvi_mean": 0.31,
                "ndvi_min": 0.22,
                "ndvi_max": 0.40,
                "ndvi_std": 0.04,
                "evi_mean": None,
                "tcg_mean": None,
                "cloud_coverage": 5.0,
                "status": "poor",
                "source": "synthetic",
            },
            {
                "date": "2024-03-11",
                "ndvi_mean": 0.48,
                "ndvi_min": 0.40,
                "ndvi_max": 0.56,
                "ndvi_std": 0.05,
                "evi_mean": None,
                "tcg_mean": None,
                "cloud_coverage": 3.0,
                "status": "moderate",
                "source": "synthetic",
            },
        ]

        response = self.client.post(
            f"/api/v1/ndvi/fields/{self.field.id}/fetch/",
            {
                "date_from": "2024-03-01",
                "date_to": "2024-03-31",
                "force_refresh": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["new_records"], 2)
        self.assertEqual(NDVIRecord.objects.count(), 2)

    def test_timeseries(self):
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-03-01",
            ndvi_mean=0.30,
            status="poor",
            source="synthetic",
        )
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-03-11",
            ndvi_mean=0.45,
            status="moderate",
            source="synthetic",
        )

        response = self.client.get(
            f"/api/v1/ndvi/fields/{self.field.id}/timeseries/?date_from=2024-03-01&date_to=2024-03-31"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["count"], 2)

    def test_analysis(self):
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-03-01",
            ndvi_mean=0.25,
            status="poor",
            source="synthetic",
        )
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-03-11",
            ndvi_mean=0.55,
            status="moderate",
            source="synthetic",
        )

        response = self.client.get(
            f"/api/v1/ndvi/fields/{self.field.id}/analysis/?date_from=2024-03-01&date_to=2024-03-31"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("analysis", response.data)
        self.assertIn("trend", response.data["analysis"])

    @override_settings(NDVI_DATA_SOURCE="synthetic")
    def test_map_requires_sentinel_mode(self):
        response = self.client.get(
            f"/api/v1/ndvi/fields/{self.field.id}/map/?date=2024-07-01"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
