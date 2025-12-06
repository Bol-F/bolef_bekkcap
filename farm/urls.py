from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FarmViewSet,
    FieldViewSet,
    CropViewSet,
    AnimalViewSet,
    ActivityLogViewSet,
    UserProfileViewSet,
)

router = DefaultRouter()
router.register(r"farms", FarmViewSet, basename="farm")
router.register(r"fields", FieldViewSet, basename="field")
router.register(r"crops", CropViewSet, basename="crop")
router.register(r"animals", AnimalViewSet, basename="animal")
router.register(r"activities", ActivityLogViewSet, basename="activity")
router.register(r"profile", UserProfileViewSet, basename="profile")

urlpatterns = [
    path("", include(router.urls)),
]
