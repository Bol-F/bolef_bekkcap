from django.urls import path

from .views import (
    AdHocNDVIQueryView,
    FarmNDVIFetchAllView,
    FieldAnalysisView,
    FieldNDVIFetchView,
    FieldNDVIMapView,
    FieldTimeSeriesView,
    HealthCheckView,
)

app_name = "ndvi"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path(
        "fields/<int:field_id>/fetch/", FieldNDVIFetchView.as_view(), name="field-fetch"
    ),
    path(
        "fields/<int:field_id>/timeseries/",
        FieldTimeSeriesView.as_view(),
        name="field-timeseries",
    ),
    path(
        "fields/<int:field_id>/analysis/",
        FieldAnalysisView.as_view(),
        name="field-analysis",
    ),
    path(
        "fields/<int:field_id>/analyze/",
        FieldAnalysisView.as_view(),
        name="field-analyze-alias",
    ),
    path("fields/<int:field_id>/map/", FieldNDVIMapView.as_view(), name="field-map"),
    path(
        "farms/<int:farm_id>/fetch-all/",
        FarmNDVIFetchAllView.as_view(),
        name="farm-fetch-all",
    ),
    path("query/", AdHocNDVIQueryView.as_view(), name="adhoc-query"),
]
