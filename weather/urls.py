from django.urls import path

from .views import (
    FieldForecastView,
    FieldIrrigationPlanView,
    FieldLatestIrrigationPlanView,
    FieldLatestWeatherView,
    FieldWeatherAdviceView,
    WeatherHealthView,
)

app_name = "weather"

urlpatterns = [
    path("health/", WeatherHealthView.as_view(), name="health"),
    path("fields/<int:field_id>/forecast/", FieldForecastView.as_view(), name="field-forecast"),
    path("fields/<int:field_id>/latest/", FieldLatestWeatherView.as_view(), name="field-latest-weather"),
    path("fields/<int:field_id>/irrigation-plan/", FieldIrrigationPlanView.as_view(), name="field-irrigation-plan"),
    path("fields/<int:field_id>/irrigation-plan/latest/", FieldLatestIrrigationPlanView.as_view(), name="field-latest-irrigation-plan"),
    path("fields/<int:field_id>/advice/", FieldWeatherAdviceView.as_view(), name="field-weather-advice"),
]