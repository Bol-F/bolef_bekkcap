from django.urls import path

from .views import (
    AdHocNDVIQueryView,
    FieldAnalysisView,
    FieldNDVIFetchView,
    FieldNDVIMapView,
    FieldTimeSeriesView,
    HealthCheckView,
)

app_name = "ndvi"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    # NDVI for existing farm.Field
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
    path("fields/<int:field_id>/map/", FieldNDVIMapView.as_view(), name="field-map"),
    # Ad-hoc polygon query
    path("query/", AdHocNDVIQueryView.as_view(), name="adhoc-query"),
]
