from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
import re
from rest_framework import serializers

from .models import Farmer, User, Ward


def normalize_kenyan_phone(value):
    if not re.fullmatch(r"\+?[\d()\s-]+", value):
        raise serializers.ValidationError(
            "Enter a Kenyan phone number like 0712 345 678."
        )
    digits = re.sub(r"\D", "", value)
    if digits.startswith("254"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[17]\d{8}", digits):
        raise serializers.ValidationError(
            "Enter a Kenyan phone number like 0712 345 678."
        )
    return f"+254{digits}"


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_phone(self, value):
        return normalize_kenyan_phone(value)


class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta:
        model = User
        fields = (
            "id",
            "phone",
            "password",
            "role",
            "language",
            "channel_preference",
            "consent_sms",
            "assigned_wards",
            "first_name",
            "last_name",
            "is_active",
        )

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farmer
        fields = "__all__"

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.role == User.Role.FARMER:
            for name in ("user", "ward", "registered_by"):
                fields[name].read_only = True
        return fields

    def validate(self, attrs):
        user = attrs.get("user", getattr(self.instance, "user", None))
        registered_by = attrs.get(
            "registered_by", getattr(self.instance, "registered_by", None)
        )
        if user and user.role != User.Role.FARMER:
            raise serializers.ValidationError({"user": "The linked user must have the FARMER role."})
        if registered_by and registered_by.role != User.Role.OFFICER:
            raise serializers.ValidationError(
                {"registered_by": "The registering user must have the OFFICER role."}
            )
        return attrs


class FarmerRegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    full_name = serializers.CharField(max_length=150)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    crop = serializers.IntegerField(min_value=1)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    consent_sms = serializers.BooleanField()

    def validate_phone(self, value):
        value = normalize_kenyan_phone(value)
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account already uses this phone number.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        if not attrs["consent_sms"]:
            raise serializers.ValidationError(
                {"consent_sms": "Agree to receive farm warnings by SMS to continue."}
            )
        name = " ".join(attrs["full_name"].split())
        if not name:
            raise serializers.ValidationError({"full_name": "Enter your full name."})
        attrs["full_name"] = name
        return attrs

    def create(self, validated_data):
        from decimal import Decimal

        from django.db import transaction
        from django.utils import timezone
        from farms.models import Farm

        validated_data.pop("password_confirm")
        validated_data.pop("consent_sms")
        password = validated_data.pop("password")
        name_parts = validated_data.pop("full_name").split(" ", 1)
        ward = validated_data["ward"]
        crop = validated_data.pop("crop")
        with transaction.atomic():
            user = User.objects.create_user(
                phone=validated_data["phone"],
                password=password,
                first_name=name_parts[0],
                last_name=name_parts[1] if len(name_parts) > 1 else "",
                role=User.Role.FARMER,
                language=User.Language.EN,
                channel_preference=User.ChannelPreference.SMS,
                consent_sms=True,
                consent_sms_at=timezone.now(),
            )
            farmer = Farmer.objects.create(
                user=user,
                ward=ward,
                main_crop=crop,
                literacy_level=Farmer.LiteracyLevel.MEDIUM,
                has_smartphone=True,
            )
            farm = Farm.objects.create(
                farmer=farmer,
                name="My farm",
                lat=ward.lat,
                lng=ward.lng,
                size_acres=Decimal("0.00"),
                slope_class=Farm.SlopeClass.GENTLE,
                soil_type="Not set",
            )
        self.farm = farm
        return user

    def validate_crop(self, value):
        from farms.models import Crop

        try:
            return Crop.objects.get(pk=value)
        except Crop.DoesNotExist as error:
            raise serializers.ValidationError("Choose a crop from the list.") from error

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Use at least 8 characters.")
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
        return value


class OfficerFarmerRegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    language = serializers.ChoiceField(choices=User.Language.choices, default=User.Language.EN)
    channel_preference = serializers.ChoiceField(
        choices=User.ChannelPreference.choices, default=User.ChannelPreference.SMS
    )
    consent_sms = serializers.BooleanField()
    literacy_level = serializers.ChoiceField(choices=Farmer.LiteracyLevel.choices)
    has_smartphone = serializers.BooleanField(default=False)

    def validate_phone(self, value):
        value = normalize_kenyan_phone(value)
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account already uses this phone number.")
        return value
