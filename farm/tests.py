from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import ActivityLog, Animal, Crop, Farm, Field
from .serializers import ActivityLogSerializer

User = get_user_model()


class ActivityLogSerializerValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner", email="owner@example.com", password="pass12345"
        )
        self.farm = Farm.objects.create(owner=self.user, name="Farm")
        self.field = Field.objects.create(
            farm=self.farm, name="Field A", area="10.00", soil_type="loam"
        )

    def test_partial_update_uses_instance_farm_when_not_provided(self):
        log = ActivityLog.objects.create(
            farm=self.farm,
            date=date(2024, 1, 1),
            activity_type="watering",
            field=self.field,
            created_by=self.user,
        )

        serializer = ActivityLogSerializer(
            instance=log,
            data={"description": "updated"},
            partial=True,
            context={"request": self._request_with_user(self.user)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    @staticmethod
    def _request_with_user(user):
        class Request:  # lightweight request stub for serializer context
            def __init__(self, user):
                self.user = user

        return Request(user)


class ActivityLogViewSetQueryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="owner2", email="owner2@example.com", password="pass12345"
        )
        self.client.force_authenticate(self.user)

        farm = Farm.objects.create(owner=self.user, name="Main farm")
        field = Field.objects.create(
            farm=farm, name="North", area="3.50", soil_type="loam"
        )
        crop = Crop.objects.create(field=field, name="Corn", status="growing")
        animal = Animal.objects.create(farm=farm, species="Cow", tag_id="A-1")

        for day in range(1, 4):
            ActivityLog.objects.create(
                farm=farm,
                field=field,
                crop=crop,
                animal=animal,
                date=date(2024, 1, day),
                activity_type="feeding",
                description=f"log {day}",
                created_by=self.user,
            )

    def test_activity_list_has_constant_query_count(self):
        url = reverse("activity-list")
        with self.assertNumQueries(2):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = (
            response.data.get("results", response.data)
            if hasattr(response.data, "get")
            else response.data
        )
        self.assertEqual(len(payload), 3)
