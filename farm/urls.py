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
    AIAnalyzeView,
    ActivityLogViewSet,
    AnimalViewSet,
    CropViewSet,
    FarmViewSet,
    FieldViewSet,
    FieldWateringStatusView,
    IoTDevicesTelemetryView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PredictYieldView,
    RegisterView,
    UserProfileViewSet,
    YieldRecordViewSet,
    me,
)

app_name = "farm"

router = DefaultRouter()
router.register(r"farms", FarmViewSet, basename="farm")
router.register(r"fields", FieldViewSet, basename="field")
router.register(r"crops", CropViewSet, basename="crop")
router.register(r"animals", AnimalViewSet, basename="animal")
router.register(r"activities", ActivityLogViewSet, basename="activity")
router.register(r"yield-records", YieldRecordViewSet, basename="yield-record")
router.register(r"profiles", UserProfileViewSet, basename="profile")

urlpatterns = [
    # profile / current user
    path("profiles/me/", me, name="profiles-me"),
    # auth
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/set-password/", set_password, name="auth-set-password"),
    # google auth
    path("auth/google/", GoogleLogin.as_view(), name="google-login"),
    path(
        "auth/google/exchange-code/",
        exchange_google_code,
        name="exchange-google-code",
    ),
    # email otp
    path("auth/email/send-code/", send_email_code, name="send-email-code"),
    path("auth/email/verify-code/", verify_email_code, name="verify-email-code"),
    # password reset
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # custom domain endpoints
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
    path("analyze/", AIAnalyzeView.as_view(), name="ai-analyze"),
    path("analyze", AIAnalyzeView.as_view(), name="ai-analyze-no-slash"),
    path("chat/", AIAnalyzeView.as_view(), name="ai-chat"),
    path("chat", AIAnalyzeView.as_view(), name="ai-chat-no-slash"),
    path("backend_analyze/", AIAnalyzeView.as_view(), name="ai-backend-analyze"),
    path("backend_analyze", AIAnalyzeView.as_view(), name="ai-backend-analyze-no-slash"),
    path(
        "iot/devices/telemetry/",
        IoTDevicesTelemetryView.as_view(),
        name="iot-devices-telemetry",
    ),
    path(
        "iot/devices/telemetry",
        IoTDevicesTelemetryView.as_view(),
        name="iot-devices-telemetry-no-slash",
    ),
    path("iot/devices/", IoTDevicesTelemetryView.as_view(), name="iot-devices"),
    path("iot/devices", IoTDevicesTelemetryView.as_view(), name="iot-devices-no-slash"),
    path("iot/telemetry/", IoTDevicesTelemetryView.as_view(), name="iot-telemetry"),
    path("iot/telemetry", IoTDevicesTelemetryView.as_view(), name="iot-telemetry-no-slash"),
    # CRUD routers
    path("", include(router.urls)),
]
