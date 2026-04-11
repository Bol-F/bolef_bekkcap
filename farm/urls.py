from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .auth_views import GoogleLogin, exchange_google_code, set_password
from .email_otp_views import send_email_code, verify_email_code
from .views import (
    ActivityLogViewSet,
    AnimalViewSet,
    CropViewSet,
    FarmViewSet,
    FieldViewSet,
    FieldWateringStatusView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PredictYieldView,
    RegisterView,
    UserProfileViewSet,
    YieldRecordViewSet,
    me,
)

router = DefaultRouter()
router.register(r"farms", FarmViewSet, basename="farm")
router.register(r"fields", FieldViewSet, basename="field")
router.register(r"crops", CropViewSet, basename="crop")
router.register(r"animals", AnimalViewSet, basename="animal")
router.register(r"activities", ActivityLogViewSet, basename="activity")
router.register(r"yield-records", YieldRecordViewSet, basename="yield-record")
router.register(r"profiles", UserProfileViewSet, basename="profile")

urlpatterns = [
    path("profiles/me/", me, name="profiles-me"),

    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/set-password/", set_password, name="auth-set-password"),

    path("auth/google/", GoogleLogin.as_view(), name="google-login"),
    path(
        "auth/google/exchange-code/",
        exchange_google_code,
        name="exchange-google-code",
    ),

    path("auth/email/send-code/", send_email_code, name="send_email_code"),
    path("auth/email/verify-code/", verify_email_code, name="verify_email_code"),

    path(
        "yield-records/<int:pk>/predict/",
        PredictYieldView.as_view(),
        name="yield-record-predict",
    ),
    path(
        "fields/<int:pk>/watering-status/",
        FieldWateringStatusView.as_view(),
        name="field-watering-status",
    ),

    path("", include(router.urls)),

    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]