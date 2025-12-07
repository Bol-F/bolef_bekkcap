from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    ActivityLogViewSet,
    AnimalViewSet,
    CropViewSet,
    FarmViewSet,
    FieldViewSet,
    LogoutView,
    RegisterView,
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
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("", include(router.urls)),
]
