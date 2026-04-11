from rest_framework.test import APITestCase
from rest_framework import status
from .models import Field, NDVIRecord


class HealthEndpointTest(APITestCase):
    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")


class FieldFlowTest(APITestCase):
    def setUp(self):
        self.payload = {
            "name": "Test Field",
            "description": "Demo polygon",
            "polygon": [
                [69.2400, 41.2990],
                [69.2500, 41.2990],
                [69.2500, 41.3050],
                [69.2400, 41.3050],
            ],
        }

    def test_create_field(self):
        response = self.client.post("/api/fields/", self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Field.objects.count(), 1)
        self.assertEqual(Field.objects.first().name, "Test Field")

    def test_list_fields(self):
        self.client.post("/api/fields/", self.payload, format="json")
        response = self.client.get("/api/fields/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_field_detail(self):
        create_response = self.client.post("/api/fields/", self.payload, format="json")
        field_id = create_response.data["id"]

        response = self.client.get(f"/api/fields/{field_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Field")

    def test_delete_field(self):
        create_response = self.client.post("/api/fields/", self.payload, format="json")
        field_id = create_response.data["id"]

        response = self.client.delete(f"/api/fields/{field_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Field.objects.count(), 0)


class AnalysisTest(APITestCase):
    def setUp(self):
        self.field = Field.objects.create(
            name="Analysis Field",
            description="For test",
            polygon=[
                [69.2400, 41.2990],
                [69.2500, 41.2990],
                [69.2500, 41.3050],
                [69.2400, 41.3050],
                [69.2400, 41.2990],
            ],
        )

        NDVIRecord.objects.create(
            field=self.field,
            date="2024-03-01",
            ndvi_mean=0.22,
            ndvi_min=0.18,
            ndvi_max=0.28,
            ndvi_std=0.03,
            status="poor",
            source="synthetic",
        )
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-04-01",
            ndvi_mean=0.41,
            ndvi_min=0.35,
            ndvi_max=0.47,
            ndvi_std=0.04,
            status="moderate",
            source="synthetic",
        )
        NDVIRecord.objects.create(
            field=self.field,
            date="2024-05-01",
            ndvi_mean=0.67,
            ndvi_min=0.61,
            ndvi_max=0.73,
            ndvi_std=0.04,
            status="healthy",
            source="synthetic",
        )

    def test_timeseries(self):
        response = self.client.get(
            f"/api/fields/{self.field.id}/timeseries/?date_from=2024-03-01&date_to=2024-05-31"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_analysis(self):
        response = self.client.get(
            f"/api/fields/{self.field.id}/analysis/?date_from=2024-03-01&date_to=2024-05-31"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("analysis", response.data)
        self.assertIn("trend", response.data["analysis"])
