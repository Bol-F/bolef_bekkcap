import hashlib
import secrets
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import EmailOTP

User = get_user_model()


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _gen_code() -> str:
    # 000000 .. 999999
    return f"{secrets.randbelow(1_000_000):06d}"


def create_and_send_otp(user) -> bool:
    """
    Creates a new OTP for user's email and sends it via SMTP.
    Stores only sha256(code).
    """
    email = (getattr(user, "email", "") or "").strip().lower()
    if not email:
        return False

    # Delete old unused codes for same user+email
    EmailOTP.objects.filter(user=user, email=email, used=False).delete()

    code = _gen_code()
    otp = EmailOTP.objects.create(
        user=user,
        email=email,
        code_hash=_hash(code),
        expires_at=timezone.now() + timedelta(minutes=10),
        attempts_left=5,
        used=False,
    )

    try:
        send_mail(
            subject="Your verification code",
            message=f"Your verification code: {code}\nValid for 10 minutes.",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[email],
            fail_silently=False,
        )
        return True
    except Exception:
        otp.delete()
        return False


@api_view(["POST"])
@permission_classes([AllowAny])
def send_email_code(request):
    """
    POST {"email":"user@example.com"}
    Sends OTP to existing user by email.
    """
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"detail": "email is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = User.objects.filter(email__iexact=email).order_by("-id")
    if not qs.exists():
        return Response(
            {"detail": "User with this email not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if qs.count() > 1:
        return Response(
            {"detail": "Multiple users with this email. Fix duplicates in DB."},
            status=status.HTTP_409_CONFLICT,
        )

    user = qs.first()

    ok = create_and_send_otp(user)
    if not ok:
        return Response(
            {"detail": "Cannot send code. Check SMTP settings."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"detail": "Verification code sent"},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_code(request):
    """
    POST {"email":"...", "code":"123456"}
    Marks EmailAddress verified, and activates user (is_active=True).
    """
    email = (request.data.get("email") or "").strip().lower()
    code = (request.data.get("code") or "").strip()

    if not email or not code:
        return Response(
            {"detail": "email and code are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = User.objects.filter(email__iexact=email).order_by("-id")
    if not qs.exists():
        return Response(
            {"detail": "User with this email not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if qs.count() > 1:
        return Response(
            {"detail": "Multiple users with this email. Fix duplicates in DB."},
            status=status.HTTP_409_CONFLICT,
        )

    user = qs.first()

    otp = (
        EmailOTP.objects.filter(user=user, email=email, used=False)
        .order_by("-created_at")
        .first()
    )
    if not otp:
        return Response(
            {"detail": "No active code found. Send a new code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if otp.is_expired():
        otp.used = True
        otp.save(update_fields=["used"])
        return Response(
            {"detail": "Code expired. Send a new code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if otp.attempts_left <= 0:
        otp.used = True
        otp.save(update_fields=["used"])
        return Response(
            {"detail": "Too many attempts. Send a new code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if _hash(code) != otp.code_hash:
        otp.attempts_left -= 1
        otp.save(update_fields=["attempts_left"])
        return Response(
            {"detail": "Invalid code"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # success
    otp.used = True
    otp.save(update_fields=["used"])

    EmailAddress.objects.update_or_create(
        user=user,
        email=email,
        defaults={"verified": True, "primary": True},
    )

    # activate account if needed
    if hasattr(user, "is_active") and user.is_active is False:
        user.is_active = True
        user.save(update_fields=["is_active"])

    return Response(
        {"detail": "Email verified"},
        status=status.HTTP_200_OK,
    )
