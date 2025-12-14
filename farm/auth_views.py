import json
import requests

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import (
    OAuth2Client as AllauthOAuth2Client,
)
from dj_rest_auth.registration.views import SocialLoginView

from django.contrib.auth.password_validation import validate_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class PatchedOAuth2Client(AllauthOAuth2Client):
    def __init__(self, request, consumer_key, consumer_secret, **kwargs):
        kwargs.pop("scope_delimiter", None)
        super().__init__(request, consumer_key, consumer_secret, **kwargs)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = PatchedOAuth2Client


@csrf_exempt
@require_POST
def exchange_google_code(request):
    """
    POST {"code": "..."}
    Exchanges code -> access_token/id_token using SocialApp credentials.
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    code = data.get("code")
    if not code:
        return JsonResponse({"detail": "code is required"}, status=400)

    try:
        app = SocialApp.objects.get(provider="google")
    except SocialApp.DoesNotExist:
        return JsonResponse(
            {"detail": "SocialApp(provider='google') not configured"}, status=500
        )

    redirect_uri = getattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/google/callback/",
    )

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": app.client_id,
            "client_secret": app.secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )

    try:
        token_data = token_resp.json()
    except Exception:
        return JsonResponse(
            {"detail": "Google token response not JSON", "raw": token_resp.text},
            status=500,
        )

    if token_resp.status_code != 200:
        return JsonResponse({"google_error": token_data}, status=400)

    return JsonResponse(token_data, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_password(request):
    """
    POST {"password":"...", "password2":"..."}
    Requires: Authorization: Bearer <access>
    Works for Google-created users too.
    """
    password = request.data.get("password") or ""
    password2 = request.data.get("password2") or ""

    if password != password2:
        return Response({"detail": "Passwords do not match"}, status=400)

    validate_password(password, request.user)

    request.user.set_password(password)
    request.user.save(update_fields=["password"])

    return Response({"detail": "Password set"}, status=200)
