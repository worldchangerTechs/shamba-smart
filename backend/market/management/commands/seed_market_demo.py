from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Farmer, Ward
from farms.models import Crop
from market.models import Buyer, MarketPrice, SellListing, TrainingEvent


HORTICULTURE_CROPS = [
    ("Tomato", "Nyanya", "Chinyanya", "Moderate", 5.5, 7.0, 120, 75),
    ("Cabbage", "Kabichi", "Ekerandi", "High", 6.0, 7.0, 45, 32),
    ("Kale", "Sukuma wiki", "Egesagani", "Moderate", 5.5, 7.0, 55, 35),
    ("Spinach", "Mchicha", "Enderema", "High", 6.0, 7.0, 70, 45),
    ("Carrot", "Karoti", "Ekaroti", "Moderate", 6.0, 6.8, 85, 55),
    ("Onion", "Kitunguu", "Chinguru", "Moderate", 6.0, 7.0, 100, 65),
    ("Potato", "Viazi", "Ebiratata", "Moderate", 5.0, 6.5, 65, 42),
    ("Avocado", "Parachichi", "Omochogoti", "Moderate", 5.5, 7.0, 90, 60),
    ("Banana", "Ndizi", "Ebitoke", "High", 5.5, 7.0, 48, 30),
    ("Passion fruit", "Pasioni", "Chibamunyinyi", "Moderate", 6.0, 7.0, 140, 90),
    ("Beans", "Maharagwe", "Chinsarate", "Moderate", 5.5, 6.8, 110, 72),
    ("Peas", "Njegere", "Ebisara", "Moderate", 6.0, 7.0, 130, 85),
    ("Capsicum", "Pilipili hoho", "Ebitunguru", "Moderate", 5.5, 6.8, 160, 105),
    ("French beans", "Maharagwe ya kijani", "Chinsarate", "High", 6.0, 7.0, 150, 95),
    ("Mango", "Embe", "Omoembe", "Low", 5.5, 7.5, 70, 45),
]

WARD_MARKETS = {
    "Kisii Central": ("Kisii Main Market", Decimal("1.10")),
    "Nyamache": ("Nyamache Market", Decimal("0.96")),
    "Bobasi": ("Ogembo Market", Decimal("1.02")),
    "Bomachoge": ("Etago Market", Decimal("0.94")),
    "Marani": ("Marani Market", Decimal("0.92")),
    "Masaba South": ("Keroka Market", Decimal("1.04")),
}

BUYER_DATA = [
    ("SAMPLE Kisii Fresh Produce Cooperative", Buyer.BuyerType.COOPERATIVE, "Kisii Central", [0, 1, 2, 3, 4, 5, 6]),
    ("SAMPLE Gusii Growers Aggregator", Buyer.BuyerType.AGGREGATOR, "Bobasi", [0, 1, 2, 8, 9, 12, 13]),
    ("SAMPLE Highlands Horticulture Export", Buyer.BuyerType.EXPORTER, "Kisii Central", [7, 9, 12, 13]),
    ("SAMPLE Gusii Town Hotel", Buyer.BuyerType.HOTEL, "Kisii Central", [0, 1, 2, 3, 8]),
    ("SAMPLE Kisii Market Supermarket", Buyer.BuyerType.SUPERMARKET, "Kisii Central", [0, 1, 2, 3, 4, 5, 6, 7, 8]),
    ("SAMPLE Nyamache Farm Aggregators", Buyer.BuyerType.AGGREGATOR, "Nyamache", [0, 1, 2, 6, 10, 11, 13]),
    ("SAMPLE Marani Vegetable Cooperative", Buyer.BuyerType.COOPERATIVE, "Marani", [0, 1, 2, 3, 4, 5, 10]),
    ("SAMPLE South Gusii Fruit Buyers", Buyer.BuyerType.EXPORTER, "Masaba South", [7, 8, 9, 14]),
    ("SAMPLE Ogembo Hospitality Buyers", Buyer.BuyerType.HOTEL, "Bobasi", [0, 1, 2, 8, 14]),
    ("SAMPLE Bomachoge Produce Store", Buyer.BuyerType.SUPERMARKET, "Bomachoge", [0, 1, 2, 4, 5, 6, 8]),
]


class Command(BaseCommand):
    help = "Seed clearly labelled sample Kisii horticulture prices, buyers, and events."

    @transaction.atomic
    def handle(self, *args, **options):
        wards = {ward.name: ward for ward in Ward.objects.all()}
        missing_wards = set(WARD_MARKETS) - set(wards)
        if missing_wards:
            self.stderr.write(
                self.style.ERROR(
                    "Create demo wards first with seed_demo. Missing: "
                    + ", ".join(sorted(missing_wards))
                )
            )
            return

        crops = {}
        for name, sw, guz, water, ph_min, ph_max, _price, _middleman in HORTICULTURE_CROPS:
            crops[name], _ = Crop.objects.update_or_create(
                name=name,
                defaults={
                    "local_name_sw": sw,
                    "local_name_guz": guz,
                    "water_needs": water,
                    "ideal_ph_min": ph_min,
                    "ideal_ph_max": ph_max,
                    "common_pests": [],
                    "common_diseases": [],
                },
            )

        today = timezone.localdate()
        price_count = 0
        for crop_index, record in enumerate(HORTICULTURE_CROPS):
            name, _sw, _guz, _water, _ph_min, _ph_max, base_price, _middleman = record
            crop = crops[name]
            for ward_index, (ward_name, (market_name, ward_factor)) in enumerate(
                WARD_MARKETS.items()
            ):
                for week_index in range(5):
                    date = today - timedelta(days=7 * (4 - week_index))
                    weekly_factor = Decimal("1") + Decimal(week_index) * Decimal("0.018")
                    crop_factor = Decimal("1") + Decimal(crop_index % 4) * Decimal("0.012")
                    price = (
                        Decimal(base_price)
                        * ward_factor
                        * weekly_factor
                        * crop_factor
                    ).quantize(Decimal("0.01"))
                    MarketPrice.objects.update_or_create(
                        crop=crop,
                        market_name=market_name,
                        ward=wards[ward_name],
                        date=date,
                        defaults={
                            "price_per_kg": price,
                            "is_sample_data": True,
                        },
                    )
                    price_count += 1

        buyer_count = 0
        for name, buyer_type, ward_name, crop_indexes in BUYER_DATA:
            buyer, _ = Buyer.objects.update_or_create(
                name=name,
                defaults={
                    "type": buyer_type,
                    "contact": "SAMPLE CONTACT - replace before launch",
                    "ward": wards[ward_name],
                    "verified": True,
                    "is_sample_data": True,
                },
            )
            buyer.crops.set(crops[HORTICULTURE_CROPS[index][0]] for index in crop_indexes)
            buyer_count += 1

        event_data = [
            (
                "SAMPLE Kisii horticulture grading workshop",
                10,
                "SAMPLE County agricultural extension",
                "TRAINING",
                "Kisii Central",
            ),
            (
                "SAMPLE Gusii produce trade day",
                24,
                "SAMPLE Kisii horticulture cooperative",
                "TRADE_EVENT",
                "Bobasi",
            ),
            (
                "SAMPLE post-harvest handling field day",
                38,
                "SAMPLE local extension partners",
                "TRAINING",
                "Nyamache",
            ),
        ]
        for title, days, host, event_type, ward_name in event_data:
            TrainingEvent.objects.update_or_create(
                title=title,
                defaults={
                    "date": timezone.now() + timedelta(days=days),
                    "ward": wards[ward_name],
                    "host": host,
                    "link": "",
                    "event_type": event_type,
                    "is_sample_data": True,
                },
            )

        farmer_rows = 0
        for index in range(1, 7):
            farmer = Farmer.objects.filter(user__phone=f"+254720{index:06d}").first()
            if not farmer:
                continue
            crop_name = HORTICULTURE_CROPS[index - 1][0]
            crop = crops[crop_name]
            SellListing.objects.update_or_create(
                farmer=farmer,
                crop=crop,
                is_sample_data=True,
                defaults={
                    "quantity_kg": Decimal(80 + index * 20),
                    "harvest_date": today + timedelta(days=14 + index),
                    "asking_price_per_kg": Decimal(
                        HORTICULTURE_CROPS[index - 1][6]
                    ),
                    "status": SellListing.Status.OPEN,
                },
            )
            farmer_rows += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sample market data ready: {len(crops)} crops, {price_count} sample "
                f"prices, {buyer_count} sample buyers, 3 sample events, "
                f"{farmer_rows} sample listings."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "All seeded market prices, buyers, events, and listings are sample data. "
                "Replace buyer contacts and independently verify buyers before production."
            )
        )
