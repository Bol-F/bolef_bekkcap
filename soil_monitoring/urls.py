from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SoilMeasurementViewSet

app_name = "soil_monitoring"

router = DefaultRouter()
router.register(r"measurements", SoilMeasurementViewSet, basename="soil-measurement")

urlpatterns = [
    path("", include(router.urls)),
]
