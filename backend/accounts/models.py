from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class Ward(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sub_county = models.CharField(max_length=120)
    lat = models.FloatField()
    lng = models.FloatField()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required.")
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields["role"] = User.Role.ADMIN
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("Superusers must have staff and superuser permissions.")
        return self.create_user(phone, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        FARMER = "FARMER", "Farmer"
        OFFICER = "OFFICER", "Officer"
        ADMIN = "ADMIN", "Admin"

    class Language(models.TextChoices):
        EN = "en", "English"
        SW = "sw", "Swahili"
        GUZ = "guz", "Ekegusii"

    class ChannelPreference(models.TextChoices):
        APP = "app", "App"
        SMS = "sms", "SMS"
        VOICE = "voice", "Voice"

    username = None
    phone = models.CharField(max_length=32, unique=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.FARMER)
    language = models.CharField(max_length=3, choices=Language.choices, default=Language.EN)
    channel_preference = models.CharField(
        max_length=8, choices=ChannelPreference.choices, default=ChannelPreference.APP
    )
    consent_sms = models.BooleanField(default=False)
    consent_sms_at = models.DateTimeField(null=True, blank=True)
    assigned_wards = models.ManyToManyField(
        Ward, blank=True, related_name="officers"
    )

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.phone


class Farmer(models.Model):
    class LiteracyLevel(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="farmer_profile")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="farmers")
    main_crop = models.ForeignKey(
        "farms.Crop",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_by_farmers",
    )
    literacy_level = models.CharField(max_length=8, choices=LiteracyLevel.choices)
    has_smartphone = models.BooleanField(default=False)
    registered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registered_farmers",
        limit_choices_to={"role": User.Role.OFFICER},
    )

    def __str__(self):
        return f"Farmer {self.user.phone}"


class FailedLoginCounter(models.Model):
    class IdentityType(models.TextChoices):
        PHONE = "PHONE", "Phone"
        IP = "IP", "IP address"

    identity_type = models.CharField(max_length=5, choices=IdentityType.choices)
    identity_hash = models.CharField(max_length=64)
    failures = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("identity_type", "identity_hash"),
                name="unique_failed_login_identity",
            )
        ]

    def __str__(self):
        return f"{self.identity_type} failed-login counter"
