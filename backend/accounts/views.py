import hashlib
import hmac
import math
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from common.api import AdminOrReadOnly, ScopedModelViewSet

from .models import FailedLoginCounter, Farmer, User, Ward
from .serializers import (
    FarmerRegistrationSerializer,
    FarmerSerializer,
    LoginSerializer,
    OfficerFarmerRegistrationSerializer,
    UserSerializer,
    WardSerializer,
)

LOGIN_WINDOW = timedelta(minutes=15)
MAX_LOGIN_FAILURES = 5


def _identity_hash(identity_type, value):
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{identity_type}:{value}".encode(),
        hashlib.sha256,
    )
    return digest.hexdigest()


def _login_identities(phone, request):
    return (
        (FailedLoginCounter.IdentityType.PHONE, _identity_hash("PHONE", phone)),
        (
            FailedLoginCounter.IdentityType.IP,
            _identity_hash("IP", request.META.get("REMOTE_ADDR", "unknown")),
        ),
    )


def _get_login_counters(identities, now):
    counters = []
    for identity_type, identity_hash in sorted(identities):
        counter, _ = FailedLoginCounter.objects.select_for_update().get_or_create(
            identity_type=identity_type,
            identity_hash=identity_hash,
            defaults={"window_started_at": now},
        )
        if now - counter.window_started_at >= LOGIN_WINDOW:
            counter.failures = 0
            counter.window_started_at = now
            counter.save(update_fields=("failures", "window_started_at"))
        counters.append(counter)
    return counters


def _token_response(user, *, farm_id=None):
    refresh = RefreshToken.for_user(user)
    response = {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
    if farm_id is not None:
        response["farm_id"] = farm_id
    return response


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FarmerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            if User.objects.filter(phone=serializer.validated_data["phone"]).exists():
                return Response(
                    {"phone": ["An account already uses this phone number."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return Response(
            {
                **_token_response(user, farm_id=serializer.farm.pk),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        identities = _login_identities(phone, request)
        now = timezone.now()
        with transaction.atomic():
            counters = _get_login_counters(identities, now)
            blocked = [
                counter
                for counter in counters
                if counter.failures >= MAX_LOGIN_FAILURES
            ]
            if blocked:
                retry_after = max(
                    1,
                    math.ceil(
                        max(
                            LOGIN_WINDOW - (now - counter.window_started_at)
                            for counter in blocked
                        ).total_seconds()
                    ),
                )
                response = Response(
                    {"detail": "Too many failed sign-in attempts. Try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
                response["Retry-After"] = str(retry_after)
                return response

        password = serializer.validated_data["password"]
        user = authenticate(request, phone=phone, password=password)
        if user is None or not user.is_active:
            with transaction.atomic():
                counters = _get_login_counters(identities, timezone.now())
                for counter in counters:
                    counter.failures += 1
                    counter.save(update_fields=("failures",))
            return Response(
                {"detail": "Phone number or password is incorrect."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        FailedLoginCounter.objects.filter(
            identity_type__in=(
                FailedLoginCounter.IdentityType.PHONE,
                FailedLoginCounter.IdentityType.IP,
            ),
            identity_hash__in=[identity_hash for _, identity_hash in identities],
        ).delete()
        return Response(_token_response(user))


class WardViewSet(ScopedModelViewSet):
    queryset = Ward.objects.all()
    serializer_class = WardSerializer
    farmer_ward_paths = ("pk",)
    ward_paths = ("pk",)
    permission_classes = [AdminOrReadOnly]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Ward.objects.all()
        return super().get_queryset()


class UserViewSet(ScopedModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    farmer_user_paths = ("pk",)
    ward_paths = ("farmer_profile__ward",)
    permission_classes = [AdminOrReadOnly]


class FarmerViewSet(ScopedModelViewSet):
    queryset = Farmer.objects.select_related("user", "ward", "registered_by")
    serializer_class = FarmerSerializer
    farmer_user_paths = ("user_id",)
    ward_paths = ("ward_id",)

    def perform_create(self, serializer):
        if self.request.user.role == User.Role.FARMER:
            raise PermissionDenied("Farmers cannot create farmer profiles.")
        super().perform_create(serializer)

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request):
        if request.user.role != User.Role.OFFICER and not request.user.is_superuser:
            raise PermissionDenied("Only officers can register a farmer.")
        if request.user.role == User.Role.OFFICER:
            try:
                requested_ward = int(request.data.get("ward"))
            except (TypeError, ValueError):
                requested_ward = None
            if requested_ward is not None and not request.user.assigned_wards.filter(
                pk=requested_ward
            ).exists():
                raise PermissionDenied(
                    "You can register farmers only in your assigned wards."
                )
        serializer = OfficerFarmerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if request.user.role == User.Role.OFFICER and not request.user.assigned_wards.filter(
            pk=data["ward"].pk
        ).exists():
            raise PermissionDenied("You can register farmers only in your assigned wards.")
        with transaction.atomic():
            user = User.objects.create_user(
                phone=data["phone"],
                first_name=data.get("first_name", "").strip(),
                last_name=data.get("last_name", "").strip(),
                role=User.Role.FARMER,
                language=data["language"],
                channel_preference=data["channel_preference"],
                consent_sms=data["consent_sms"],
                consent_sms_at=timezone.now() if data["consent_sms"] else None,
            )
            farmer = Farmer.objects.create(
                user=user,
                ward=data["ward"],
                literacy_level=data["literacy_level"],
                has_smartphone=data["has_smartphone"],
                registered_by=request.user if request.user.role == User.Role.OFFICER else None,
            )
        return Response(
            FarmerSerializer(farmer, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )
