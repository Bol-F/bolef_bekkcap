from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from farm.models import Farm, Field, YieldRecord
from .models import SoilMeasurement

User = get_user_model()


class SoilMonitoringApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="soiluser",
            email="soil@example.com",
            password="Testpass123!",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.farm = Farm.objects.create(
            owner=self.user,
            name="Soil Farm",
            size_hectares="80.00",
            polygon=[
                [69.2400, 41.2990],
                [69.2700, 41.2990],
                [69.2700, 41.3200],
                [69.2400, 41.3200],
                [69.2400, 41.2990],
            ],
        )

        self.field1 = Field.objects.create(
            farm=self.farm,
            name="Field 1",
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

        self.field2 = Field.objects.create(
            farm=self.farm,
            name="Field 2",
            area="12.00",
            soil_type="clay",
            polygon=[
                [69.2560, 41.3020],
                [69.2660, 41.3020],
                [69.2660, 41.3090],
                [69.2560, 41.3090],
                [69.2560, 41.3020],
            ],
        )

        self.yield_record = YieldRecord.objects.create(
            farm=self.farm,
            field=self.field1,
            crop_type="Cotton",
            season="kharif",
            irrigation_type="drip",
            soil_type="loamy",
            farm_area_acres="25.00",
            fertilizer_used_tons="3.00",
            pesticide_used_kg="1.50",
            water_usage_cubic_meters="1000.00",
        )

        self.other_yield_record = YieldRecord.objects.create(
            farm=self.farm,
            field=self.field2,
            crop_type="Wheat",
            season="rabi",
            irrigation_type="sprinkler",
            soil_type="clay",
            farm_area_acres="15.00",
            fertilizer_used_tons="2.00",
            pesticide_used_kg="1.00",
            water_usage_cubic_meters="800.00",
        )

    def test_create_soil_measurement(self):
        payload = {
            "field": self.field1.id,
            "yield_record": self.yield_record.id,
            "soil_type": "loamy",
            "moisture_percent": "42.50",
            "ph_level": "6.80",
            "nitrogen": "20.00",
            "phosphorus": "10.00",
            "potassium": "12.00",
            "temperature_celsius": "23.50",
            "sample_date": "2026-04-10",
            "notes": "Healthy sample",
        }

        response = self.client.post(
            "/api/v1/soil/measurements/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(SoilMeasurement.objects.count(), 1)

    def test_create_soil_measurement_with_wrong_yield_record_fails(self):
        payload = {
            "field": self.field1.id,
            "yield_record": self.other_yield_record.id,
            "soil_type": "loamy",
            "moisture_percent": "42.50",
            "ph_level": "6.80",
            "nitrogen": "20.00",
            "phosphorus": "10.00",
            "potassium": "12.00",
            "temperature_celsius": "23.50",
            "sample_date": "2026-04-10",
            "notes": "Bad relation",
        }

        response = self.client.post(
            "/api/v1/soil/measurements/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("yield_record", response.data)

    def test_measurements_list_is_owner_scoped(self):
        SoilMeasurement.objects.create(
            field=self.field1,
            yield_record=self.yield_record,
            soil_type="loamy",
            sample_date="2026-04-10",
        )

        response = self.client.get("/api/v1/soil/measurements/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
