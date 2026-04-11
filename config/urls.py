from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from farm.auth_views import GoogleLogin, exchange_google_code
from farm.email_otp_views import send_email_code, verify_email_code


urlpatterns = [
    path("admin/", admin.site.urls),
    # Main API
    path("api/v1/", include("farm.urls")),
    path("api/v1/soil/", include("soil_monitoring.urls")),
    path("api/v1/ndvi/", include("ndvi.urls")),
    # dj-rest-auth
    path("dj-rest-auth/", include("dj_rest_auth.urls")),
    path("dj-rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    # Google OAuth
    path("dj-rest-auth/google/", GoogleLogin.as_view(), name="google_login"),
    path("auth/google/exchange/", exchange_google_code, name="google_exchange"),
    # Email OTP
    path("auth/email/send-code/", send_email_code, name="send_email_code"),
    path("auth/email/verify-code/", verify_email_code, name="verify_email_code"),
    # OpenAPI / Swagger / ReDoc
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="schema-swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="schema-redoc",
    ),
    # DRF browsable auth
    path("api-auth/", include("rest_framework.urls")),
]

if getattr(settings, "ENABLE_ALLAUTH_PAGES", False):
    urlpatterns += [
        path("accounts/", include("allauth.urls")),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
