from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Farm, Field

User = get_user_model()


class FarmFieldApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="Testpass123!",
        )
        self.other_user = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="Testpass123!",
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.farm_polygon = [
            [69.2400, 41.2990],
            [69.2700, 41.2990],
            [69.2700, 41.3200],
            [69.2400, 41.3200],
            [69.2400, 41.2990],
        ]

        self.farm = Farm.objects.create(
            owner=self.user,
            name="Main Farm",
            location="Tashkent",
            size_hectares="100.00",
            polygon=self.farm_polygon,
        )

    def test_create_farm_with_polygon(self):
        payload = {
            "name": "Second Farm",
            "location": "Tashkent region",
            "size_hectares": "150.00",
            "polygon": [
                [69.3000, 41.3000],
                [69.3400, 41.3000],
                [69.3400, 41.3300],
                [69.3000, 41.3300],
                [69.3000, 41.3000],
            ],
        }

        response = self.client.post("/api/v1/farms/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["name"], "Second Farm")
        self.assertTrue(response.data["has_location"])

    def test_create_field_inside_farm(self):
        payload = {
            "farm": self.farm.id,
            "name": "Field A",
            "area": "10.00",
            "soil_type": "loamy",
            "polygon": [
                [69.2450, 41.3020],
                [69.2550, 41.3020],
                [69.2550, 41.3090],
                [69.2450, 41.3090],
                [69.2450, 41.3020],
            ],
        }

        response = self.client.post("/api/v1/fields/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["name"], "Field A")
        self.assertTrue(response.data["has_location"])

    def test_create_field_outside_farm_fails(self):
        payload = {
            "farm": self.farm.id,
            "name": "Bad Field",
            "area": "10.00",
            "soil_type": "loamy",
            "polygon": [
                [69.5000, 41.5000],
                [69.5100, 41.5000],
                [69.5100, 41.5100],
                [69.5000, 41.5100],
                [69.5000, 41.5000],
            ],
        }

        response = self.client.post("/api/v1/fields/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("polygon", response.data)

    def test_create_field_bigger_than_farm_size_fails(self):
        payload = {
            "farm": self.farm.id,
            "name": "Too Big",
            "area": "150.00",
            "soil_type": "loamy",
            "polygon": [
                [69.2450, 41.3020],
                [69.2550, 41.3020],
                [69.2550, 41.3090],
                [69.2450, 41.3090],
                [69.2450, 41.3020],
            ],
        }

        response = self.client.post("/api/v1/fields/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("area", response.data)

    def test_other_user_cannot_see_my_farms(self):
        other_client = APIClient()
        other_client.force_authenticate(self.other_user)

        response = other_client.get("/api/v1/farms/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_other_user_cannot_create_field_in_my_farm(self):
        other_client = APIClient()
        other_client.force_authenticate(self.other_user)

        payload = {
            "farm": self.farm.id,
            "name": "Hack Field",
            "area": "5.00",
            "soil_type": "loamy",
            "polygon": [
                [69.2450, 41.3020],
                [69.2550, 41.3020],
                [69.2550, 41.3090],
                [69.2450, 41.3090],
                [69.2450, 41.3020],
            ],
        }

        response = other_client.post("/api/v1/fields/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)