from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from farm.auth_views import GoogleLogin, exchange_google_code
from farm.email_otp_views import send_email_code, verify_email_code

schema_view = get_schema_view(
    openapi.Info(
        title="Farm API",
        default_version="v1",
        description="API for managing farms, fields, crops, animals and activities",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API
    path("api/v1/", include("farm.urls")),
    # Auth (dj-rest-auth)
    path("dj-rest-auth/", include("dj_rest_auth.urls")),
    path("dj-rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    path("dj-rest-auth/google/", GoogleLogin.as_view(), name="google_login"),
    # Google OAuth helpers
    path(
        "auth/google/callback/",
        TemplateView.as_view(template_name="google_callback.html"),
    ),
    path("auth/google/exchange/", exchange_google_code, name="google_exchange"),
    # Email OTP
    path("auth/email/send-code/", send_email_code, name="send_email_code"),
    path("auth/email/verify-code/", verify_email_code, name="verify_email_code"),
    # Swagger / OpenAPI
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

# Only include if you really use allauth HTML pages.
# If you don't need browser pages, you can remove this line safely.
if env := getattr(settings, "ENABLE_ALLAUTH_PAGES", False):
    urlpatterns += [path("accounts/", include("allauth.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
