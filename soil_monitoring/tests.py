# from datetime import timedelta
#
# from django.contrib.auth import get_user_model
# from django.test import TestCase
# from django.urls import reverse
# from django.utils import timezone
# from rest_framework.test import APIClient
#
# from farm.models import Farm, Field
# from .models import FieldSoilProfile, Recommendation, SensorReading
#
# User = get_user_model()
#
#
# class SensorReadingQueryOptimizationTests(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.user = User.objects.create_user(
#             username="soil-owner", email="soil-owner@example.com", password="pass12345"
#         )
#         self.client.force_authenticate(self.user)
#
#         farm = Farm.objects.create(owner=self.user, name="Farm")
#         self.field = Field.objects.create(
#             farm=farm, name="A", area="10.00", soil_type="loam"
#         )
#         FieldSoilProfile.objects.create(field=self.field)
#
#         for hour in range(5):
#             SensorReading.objects.create(
#                 field=self.field,
#                 ts=timezone.now() - timedelta(hours=hour),
#                 moisture_vwc=0.25,
#                 ph=6.5,
#                 ec_ds_m=1.5,
#                 soil_temp_c=23,
#             )
#
#     def test_reading_list_does_not_have_n_plus_one_for_soil_profile(self):
#         url = reverse("soil_monitoring:sensor-reading-list")
#         with self.assertNumQueries(2):
#             response = self.client.get(url)
#
#         self.assertEqual(response.status_code, 200)
#         payload = response.data.get("results", response.data)
#         self.assertEqual(len(payload), 5)
#         self.assertIn("health_indicators", payload[0])
#
#
# class RecommendationAgeAnnotationTests(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.user = User.objects.create_user(
#             username="rec-owner", email="rec-owner@example.com", password="pass12345"
#         )
#         self.client.force_authenticate(self.user)
#
#         farm = Farm.objects.create(owner=self.user, name="Farm")
#         field = Field.objects.create(
#             farm=farm, name="B", area="12.00", soil_type="clay"
#         )
#         self.rec = Recommendation.objects.create(
#             field=field,
#             category=Recommendation.Category.SOIL_PH,
#             severity=Recommendation.Severity.MED,
#             title="Adjust pH",
#             message="Add lime.",
#             is_active=True,
#         )
#
#     def test_recommendation_list_includes_age_hours(self):
#         url = reverse("soil_monitoring:recommendation-list")
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, 200)
#         payload = response.data.get("results", response.data)
#         self.assertEqual(len(payload), 1)
#         self.assertIn("age_hours", payload[0])
