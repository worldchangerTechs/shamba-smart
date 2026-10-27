import pytest
from rest_framework.test import APIClient

from .models import Farmer, User, Ward
from farms.models import Crop, Farm, Planting


@pytest.mark.django_db
def test_phone_login_returns_jwt_and_authenticates_user():
    user = User.objects.create_user(
        phone="+254700000123",
        password="safe-demo-password",
        first_name="Amina",
    )
    client = APIClient()

    response = client.post(
        "/api/auth/token/",
        {"phone": user.phone, "password": "safe-demo-password"},
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data) == {"access", "refresh"}

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    profile_response = client.get("/api/users/")

    assert profile_response.status_code == 200
    assert profile_response.data[0]["phone"] == user.phone


@pytest.mark.django_db
def test_officer_can_register_a_basic_phone_farmer_in_assigned_ward():
    ward = Ward.objects.create(name="Kisii Central", sub_county="Kisii Central", lat=-0.68, lng=34.76)
    officer = User.objects.create_user(phone="+254700000124", role=User.Role.OFFICER)
    officer.assigned_wards.add(ward)
    client = APIClient()
    client.force_authenticate(officer)

    response = client.post(
        "/api/farmers/register/",
        {
            "phone": "+254700000125",
            "first_name": "Amina",
            "ward": ward.pk,
            "language": "sw",
            "consent_sms": True,
            "literacy_level": "LOW",
            "has_smartphone": False,
        },
        format="json",
    )

    assert response.status_code == 201
    farmer = Farmer.objects.get(user__phone="+254700000125")
    assert farmer.registered_by == officer
    assert farmer.ward == ward
    assert farmer.user.language == User.Language.SW
    assert farmer.user.consent_sms is True
    assert farmer.user.has_usable_password() is False


@pytest.mark.django_db
def test_officer_cannot_register_a_farmer_outside_assigned_wards():
    assigned = Ward.objects.create(name="Kisii Central", sub_county="Kisii Central", lat=-0.68, lng=34.76)
    other = Ward.objects.create(name="Bobasi", sub_county="Bobasi", lat=-0.72, lng=34.78)
    officer = User.objects.create_user(phone="+254700000126", role=User.Role.OFFICER)
    officer.assigned_wards.add(assigned)
    client = APIClient()
    client.force_authenticate(officer)

    response = client.post(
        "/api/farmers/register/",
        {"phone": "+254700000127", "ward": other.pk, "consent_sms": False},
        format="json",
    )

    assert response.status_code == 403
    assert not User.objects.filter(phone="+254700000127").exists()


@pytest.fixture
def signup_catalog():
    ward = Ward.objects.create(
        name="Kisii Central",
        sub_county="Kisii Central",
        lat=-0.68,
        lng=34.76,
    )
    crop = Crop.objects.create(
        name="Tomato",
        water_needs="Regular",
        ideal_ph_min=5.5,
        ideal_ph_max=7.0,
    )
    return ward, crop


def signup_payload(ward, crop, **overrides):
    return {
        "full_name": "Amina Farmer",
        "phone": "0712 345 678",
        "ward": ward.pk,
        "crop": crop.pk,
        "password": "KisiiFarm$2026",
        "password_confirm": "KisiiFarm$2026",
        "consent_sms": True,
        **overrides,
    }


@pytest.mark.django_db
def test_public_registration_creates_farmer_farm_and_returns_jwt(signup_catalog):
    ward, crop = signup_catalog
    response = APIClient().post(
        "/api/auth/register/", signup_payload(ward, crop), format="json"
    )

    assert response.status_code == 201
    assert set(response.data) == {"access", "refresh", "farm_id"}
    user = User.objects.get(phone="+254712345678")
    farmer = Farmer.objects.get(user=user)
    farm = Farm.objects.get(pk=response.data["farm_id"], farmer=farmer)
    assert user.first_name == "Amina"
    assert user.last_name == "Farmer"
    assert user.consent_sms is True
    assert user.consent_sms_at is not None
    assert farmer.main_crop == crop
    assert farm.lat == ward.lat
    assert farm.lng == ward.lng
    assert farm.size_acres == 0
    assert not Planting.objects.filter(farm=farm).exists()


@pytest.mark.django_db
def test_registration_rejects_duplicate_phone_after_normalization(signup_catalog):
    ward, crop = signup_catalog
    User.objects.create_user(phone="+254712345678", password="old-password")

    response = APIClient().post(
        "/api/auth/register/", signup_payload(ward, crop), format="json"
    )

    assert response.status_code == 400
    assert "already uses" in response.data["phone"][0]


@pytest.mark.django_db
def test_registration_rejects_invalid_kenyan_phone(signup_catalog):
    ward, crop = signup_catalog

    response = APIClient().post(
        "/api/auth/register/",
        signup_payload(ward, crop, phone="12345"),
        format="json",
    )

    assert response.status_code == 400
    assert "0712 345 678" in response.data["phone"][0]
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_registration_rejects_mismatched_passwords(signup_catalog):
    ward, crop = signup_catalog

    response = APIClient().post(
        "/api/auth/register/",
        signup_payload(ward, crop, password_confirm="DifferentPass$2026"),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["password_confirm"] == ["Passwords do not match."]
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_registration_requires_sms_consent(signup_catalog):
    ward, crop = signup_catalog

    response = APIClient().post(
        "/api/auth/register/",
        signup_payload(ward, crop, consent_sms=False),
        format="json",
    )

    assert response.status_code == 400
    assert "consent_sms" in response.data
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_login_rejects_bad_phone_and_rate_limits_phone_and_ip():
    client = APIClient()
    invalid_phone = client.post(
        "/api/auth/login/",
        {"phone": "not a phone", "password": "wrong"},
        format="json",
        REMOTE_ADDR="192.0.2.10",
    )
    assert invalid_phone.status_code == 400

    for _ in range(5):
        response = client.post(
            "/api/auth/login/",
            {"phone": "0712345678", "password": "wrong"},
            format="json",
            REMOTE_ADDR="192.0.2.10",
        )
        assert response.status_code == 401

    blocked_phone = client.post(
        "/api/auth/login/",
        {"phone": "0712345678", "password": "wrong"},
        format="json",
        REMOTE_ADDR="192.0.2.11",
    )
    assert blocked_phone.status_code == 429
    assert int(blocked_phone["Retry-After"]) > 0

    blocked_ip = client.post(
        "/api/auth/login/",
        {"phone": "0712345679", "password": "wrong"},
        format="json",
        REMOTE_ADDR="192.0.2.10",
    )
    assert blocked_ip.status_code == 429


@pytest.mark.django_db
def test_login_returns_jwt_for_normalized_phone():
    User.objects.create_user(
        phone="+254712345670",
        password="KisiiFarm$2026",
    )

    response = APIClient().post(
        "/api/auth/login/",
        {"phone": "0712 345 670", "password": "KisiiFarm$2026"},
        format="json",
        REMOTE_ADDR="192.0.2.12",
    )

    assert response.status_code == 200
    assert set(response.data) == {"access", "refresh"}
