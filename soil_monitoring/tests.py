from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from farm.models import Farm, Field
from .models import FieldSoilProfile, SensorReading

User = get_user_model()


class SoilMonitoringQueryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="soil-owner", email="soil-owner@example.com", password="pass12345"
        )
        self.client.force_authenticate(self.user)

        farm = Farm.objects.create(owner=self.user, name="Soil Farm")
        self.field = Field.objects.create(
            farm=farm, name="Soil Field", area="5.00", soil_type="loam"
        )
        FieldSoilProfile.objects.create(field=self.field)

        now = timezone.now()
        for i in range(3):
            SensorReading.objects.create(
                field=self.field,
                ts=now - timedelta(hours=i),
                moisture_vwc=0.22 + i * 0.01,
                ph=6.8,
                ec_ds_m=1.2,
                soil_temp_c=22.0,
            )

    def test_sensor_readings_list_is_constant_queries(self):
        url = reverse("soil_monitoring:sensor-reading-list")
        with self.assertNumQueries(2):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.data.get("results", response.data)
        self.assertEqual(len(payload), 3)


class SoilMonitoringValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="soil-owner-2", email="soil-owner-2@example.com", password="pass12345"
        )
        self.client.force_authenticate(self.user)

        farm = Farm.objects.create(owner=self.user, name="Farm")
        self.field = Field.objects.create(
            farm=farm, name="Field", area="1.00", soil_type="loam"
        )

    def test_statistics_rejects_non_positive_days(self):
        url = reverse("soil_monitoring:analytics-statistics")
        response = self.client.get(url, {"field_id": self.field.id, "days": 0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "days must be a positive integer")

    def test_health_rejects_invalid_days(self):
        url = reverse("soil_monitoring:analytics-health")
        response = self.client.get(url, {"field_id": self.field.id, "days": "invalid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "days must be a positive integer")
