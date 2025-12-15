from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .auth_views import set_password
from .email_otp_views import send_email_code, verify_email_code
from .views import (
    ActivityLogViewSet,
    AnimalViewSet,
    CropViewSet,
    FarmViewSet,
    FieldViewSet,
    LogoutView,
    RegisterView,
    UserProfileViewSet,
    me,
)

router = DefaultRouter()
router.register(r"farms", FarmViewSet, basename="farm")
router.register(r"fields", FieldViewSet, basename="field")
router.register(r"crops", CropViewSet, basename="crop")
router.register(r"animals", AnimalViewSet, basename="animal")
router.register(r"activities", ActivityLogViewSet, basename="activity")
router.register(
    r"profiles", UserProfileViewSet, basename="profile"
)  # plural is cleaner

urlpatterns = [
    # ==========================
    # AUTH (JWT + custom)
    # ==========================
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", me, name="auth-me"),
    path("auth/set-password/", set_password, name="auth-set-password"),
    # ==========================
    # EMAIL OTP
    # ==========================
    path("auth/email/send-code/", send_email_code, name="send_email_code"),
    path("auth/email/verify-code/", verify_email_code, name="verify_email_code"),
    # ==========================
    # API resources
    # ==========================
    path("", include(router.urls)),
]
