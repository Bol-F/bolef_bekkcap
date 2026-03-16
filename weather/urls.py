from django.urls import path
from .views import FieldWeatherForecastView

app_name = "weather"

urlpatterns = [
    path("forecast/", FieldWeatherForecastView.as_view(), name="forecast"),
]