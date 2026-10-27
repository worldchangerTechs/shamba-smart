import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Farmer, User, Ward
from farms.models import Crop, Farm, Planting


WARD_DATA = [
    ("Kisii Central", "Kisii Central", -0.6773, 34.7792),
    ("Nyamache", "Nyamache", -0.8400, 34.8500),
    ("Bobasi", "Bobasi", -0.7900, 34.7200),
    ("Bomachoge", "Bomachoge", -0.7700, 34.9100),
    ("Marani", "Marani", -0.5600, 34.8000),
    ("Masaba South", "Masaba South", -0.6200, 34.7000),
]

CROP_DATA = [
    ("Maize", "Mahindi", "Ebibitindi", "Moderate", 5.5, 7.0, ["fall armyworm"], ["maize lethal necrosis"]),
    ("Beans", "Maharagwe", "Chinsarate", "Moderate", 5.5, 6.8, ["bean fly"], ["angular leaf spot"]),
    ("Tea", "Chai", "Chai", "High", 4.5, 5.5, ["tea mosquito bug"], ["blister blight"]),
    ("Banana", "Ndizi", "Ebitoke", "High", 5.5, 7.0, ["banana weevil"], ["black sigatoka"]),
    ("Potato", "Viazi", "Ebiratata", "Moderate", 5.0, 6.5, ["aphids"], ["late blight"]),
]

OFFICER_ASSIGNMENTS = {
    1: ("Kisii Central", "Nyamache"),
    2: ("Bobasi", "Bomachoge"),
    3: ("Marani", "Masaba South"),
}


class Command(BaseCommand):
    help = "Create demo Kisii wards, officers, farmers, farms, and plantings."

    @transaction.atomic
    def handle(self, *args, **options):
        wards = {}
        for name, sub_county, lat, lng in WARD_DATA:
            wards[name], _ = Ward.objects.update_or_create(
                name=name,
                defaults={"sub_county": sub_county, "lat": lat, "lng": lng},
            )

        crops = {}
        for name, sw, guz, water, ph_min, ph_max, pests, diseases in CROP_DATA:
            crops[name], _ = Crop.objects.update_or_create(
                name=name,
                defaults={
                    "local_name_sw": sw,
                    "local_name_guz": guz,
                    "water_needs": water,
                    "ideal_ph_min": ph_min,
                    "ideal_ph_max": ph_max,
                    "common_pests": pests,
                    "common_diseases": diseases,
                },
            )

        password = os.environ.get("DEMO_USER_PASSWORD")
        officers = {}
        for number, ward_names in OFFICER_ASSIGNMENTS.items():
            phone = f"+25471000000{number}"
            officer, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    "role": User.Role.OFFICER,
                    "first_name": f"Demo Officer {number}",
                    "language": User.Language.EN,
                },
            )
            if password and (created or not officer.has_usable_password()):
                officer.set_password(password)
                officer.save(update_fields=["password"])
            officer.role = User.Role.OFFICER
            officer.save(update_fields=["role"])
            officer.assigned_wards.set(wards[name] for name in ward_names)
            officers[number] = officer

        today = timezone.localdate()
        for number in range(1, 41):
            phone = f"+254720{number:06d}"
            ward_name = WARD_DATA[(number - 1) % len(WARD_DATA)][0]
            officer_number = ((number - 1) % len(WARD_DATA)) // 2 + 1
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    "role": User.Role.FARMER,
                    "first_name": f"Demo Farmer {number:02d}",
                    "language": (User.Language.EN, User.Language.SW, User.Language.GUZ)[number % 3],
                    "channel_preference": User.ChannelPreference.APP,
                    "consent_sms": number % 2 == 0,
                },
            )
            if password and (created or not user.has_usable_password()):
                user.set_password(password)
                user.save(update_fields=["password"])
            farmer, _ = Farmer.objects.update_or_create(
                user=user,
                defaults={
                    "ward": wards[ward_name],
                    "literacy_level": (Farmer.LiteracyLevel.LOW, Farmer.LiteracyLevel.MEDIUM, Farmer.LiteracyLevel.HIGH)[number % 3],
                    "has_smartphone": number % 2 == 0,
                    "registered_by": officers[officer_number],
                },
            )
            farm, _ = Farm.objects.get_or_create(
                farmer=farmer,
                name=f"Demo Farm {number:02d}",
                defaults={
                    "lat": wards[ward_name].lat + ((number % 7) - 3) * 0.001,
                    "lng": wards[ward_name].lng + ((number % 9) - 4) * 0.001,
                    "size_acres": 1 + (number % 8) / 2,
                    "slope_class": (Farm.SlopeClass.FLAT, Farm.SlopeClass.GENTLE, Farm.SlopeClass.STEEP)[number % 3],
                    "soil_type": ("clay loam", "red volcanic", "sandy loam")[number % 3],
                },
            )
            crop = crops[CROP_DATA[(number - 1) % len(CROP_DATA)][0]]
            planted_on = today - timedelta(days=number % 90)
            Planting.objects.get_or_create(
                farm=farm,
                crop=crop,
                planted_on=planted_on,
                defaults={
                    "variety": f"Demo {crop.name} variety",
                    "expected_harvest": today + timedelta(days=60 + number % 90),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(WARD_DATA)} wards, {len(CROP_DATA)} crops, "
                "40 farmers, 40 farms, 40 plantings, and 3 officers."
            )
        )
        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "Demo accounts have unusable passwords. Set DEMO_USER_PASSWORD before rerunning to enable login."
                )
            )
