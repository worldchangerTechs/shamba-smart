import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from farms.models import Crop, Farm, Planting
from market.management.commands.seed_market_demo import HORTICULTURE_CROPS
from market.models import Buyer, MarketPrice, SellListing, TrainingEvent


class MarketApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=-0.6773, lng=34.7792
        )
        cls.nearby_ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=-0.70, lng=34.78
        )
        cls.far_ward = Ward.objects.create(
            name="Nyamache", sub_county="Nyamache", lat=-0.95, lng=35.1
        )
        cls.crop = Crop.objects.create(
            name="Tomato",
            local_name_sw="Nyanya",
            water_needs="Moderate",
            ideal_ph_min=5.5,
            ideal_ph_max=7,
        )
        cls.farmer_user = User.objects.create_user(
            phone="+254720040001", role=User.Role.FARMER, first_name="Farmer A"
        )
        cls.farmer = Farmer.objects.create(
            user=cls.farmer_user,
            ward=cls.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        cls.farm = Farm.objects.create(
            farmer=cls.farmer,
            name="Tomato farm",
            lat=cls.ward.lat,
            lng=cls.ward.lng,
            size_acres=1,
            slope_class=Farm.SlopeClass.GENTLE,
            soil_type="loam",
        )
        cls.planting = Planting.objects.create(
            farm=cls.farm,
            crop=cls.crop,
            variety="Roma",
            planted_on=timezone.localdate() - timedelta(days=20),
            expected_harvest=timezone.localdate() + timedelta(days=20),
        )
        cls.officer = User.objects.create_user(
            phone="+254710040001", role=User.Role.OFFICER
        )
        cls.officer.assigned_wards.add(cls.ward)
        cls.other_officer = User.objects.create_user(
            phone="+254710040002", role=User.Role.OFFICER
        )
        cls.other_officer.assigned_wards.add(cls.nearby_ward)

    def setUp(self):
        self.client = APIClient()

    def test_price_trends_return_seven_and_thirty_day_series(self):
        today = timezone.localdate()
        for offset, price in [
            (35, "40.00"),
            (28, "45.00"),
            (21, "48.00"),
            (14, "50.00"),
            (7, "55.00"),
            (1, "60.00"),
            (0, "65.00"),
        ]:
            MarketPrice.objects.create(
                crop=self.crop,
                market_name="Kisii Main Market",
                ward=self.ward,
                price_per_kg=Decimal(price),
                date=today - timedelta(days=offset),
                is_sample_data=True,
            )
        self.client.force_authenticate(self.farmer_user)
        response = self.client.get(
            f"/api/market-prices/trends/?crop_id={self.crop.pk}&ward_id={self.ward.pk}"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["trend_7d"]["daily_prices"]), 2)
        self.assertEqual(len(response.data["trend_30d"]["daily_prices"]), 6)
        self.assertGreater(response.data["trend_7d"]["change_percent"], 0)
        self.assertTrue(response.data["is_sample_data"])

    def test_price_compare_picks_best_market_within_30_km_and_estimates_gain(self):
        today = timezone.localdate()
        for ward, market, price in (
            (self.ward, "Kisii Main", "70.00"),
            (self.nearby_ward, "Ogembo", "85.00"),
            (self.far_ward, "Distant market", "150.00"),
        ):
            MarketPrice.objects.create(
                crop=self.crop,
                market_name=market,
                ward=ward,
                price_per_kg=Decimal(price),
                date=today,
                is_sample_data=True,
            )
        self.client.force_authenticate(self.farmer_user)
        response = self.client.get(
            "/api/market-prices/compare/",
            {
                "farm_id": self.farm.pk,
                "crop_id": self.crop.pk,
                "middleman_price_per_kg": "60.00",
                "quantity_kg": "100",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["best_market"]["name"], "Ogembo")
        self.assertLessEqual(response.data["best_market"]["distance_km"], 30)
        self.assertEqual(response.data["estimated_gain"]["amount"], "2500.00")

    def test_officer_can_add_and_edit_prices_only_in_assigned_wards(self):
        self.client.force_authenticate(self.officer)
        response = self.client.post(
            "/api/market-prices/",
            {
                "crop": self.crop.pk,
                "market_name": "Kisii Main",
                "ward": self.ward.pk,
                "price_per_kg": "55.00",
                "date": timezone.localdate().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        price = MarketPrice.objects.get(pk=response.data["id"])
        self.assertFalse(price.is_sample_data)

        response = self.client.post(
            "/api/market-prices/",
            {
                "crop": self.crop.pk,
                "market_name": "Ogembo",
                "ward": self.nearby_ward.pk,
                "price_per_kg": "57.00",
                "date": timezone.localdate().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.other_officer)
        response = self.client.patch(
            f"/api/market-prices/{price.pk}/",
            {"price_per_kg": "59.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_verified_buyer_directory_filters_to_verified_records(self):
        buyer = Buyer.objects.create(
            name="Verified sample cooperative",
            type=Buyer.BuyerType.COOPERATIVE,
            contact="SAMPLE CONTACT",
            verified=True,
            is_sample_data=True,
            ward=self.ward,
        )
        buyer.crops.add(self.crop)
        Buyer.objects.create(
            name="Unverified buyer",
            type=Buyer.BuyerType.AGGREGATOR,
            contact="",
            verified=False,
        )
        self.client.force_authenticate(self.farmer_user)
        response = self.client.get("/api/buyers/")
        self.assertEqual(response.status_code, 200, response.data)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual([item["id"] for item in results], [buyer.pk])
        self.assertTrue(results[0]["is_sample_data"])

    def test_farmer_posts_listing_and_other_authenticated_users_can_browse(self):
        self.client.force_authenticate(self.farmer_user)
        response = self.client.post(
            "/api/sell-listings/",
            {
                "crop": self.crop.pk,
                "quantity_kg": "250.00",
                "harvest_date": (timezone.localdate() + timedelta(days=20)).isoformat(),
                "asking_price_per_kg": "80.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        listing = SellListing.objects.get(pk=response.data["id"])
        self.assertEqual(listing.farmer_id, self.farmer.pk)
        self.assertEqual(listing.status, SellListing.Status.OPEN)

        buyer_user = User.objects.create_user(
            phone="+254720040002", role=User.Role.FARMER
        )
        Farmer.objects.create(
            user=buyer_user,
            ward=self.nearby_ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        self.client.force_authenticate(buyer_user)
        response = self.client.get("/api/sell-listings/")
        self.assertEqual(response.status_code, 200, response.data)
        results = response.data["results"] if "results" in response.data else response.data
        self.assertIn(listing.pk, [item["id"] for item in results])

    def test_public_price_lookup_is_localized_short_and_marks_samples(self):
        MarketPrice.objects.create(
            crop=self.crop,
            market_name="Kisii Main Market",
            ward=self.ward,
            price_per_kg=Decimal("65.00"),
            date=timezone.localdate(),
            is_sample_data=True,
        )
        response = self.client.get(
            "/api/gateway/market-price/",
            {"crop": "Nyanya", "ward": "Kisii Central", "language": "sw"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_sample_data"])
        self.assertEqual(response.data["average_price_per_kg"], "65.00")
        self.assertEqual(response.data["crop_local_name"], "Nyanya")
        self.assertLessEqual(len(response.data["sms_text"]), 160)
        self.assertIn("Bei za mfano", response.data["ussd_text"])


class MarketManagementCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wards = [
            ("Kisii Central", -0.6773, 34.7792),
            ("Nyamache", -0.84, 34.85),
            ("Bobasi", -0.79, 34.72),
            ("Bomachoge", -0.77, 34.91),
            ("Marani", -0.56, 34.8),
            ("Masaba South", -0.62, 34.7),
        ]
        for name, lat, lng in wards:
            Ward.objects.create(name=name, sub_county=name, lat=lat, lng=lng)

    def test_seed_market_demo_creates_fifteen_crop_catalog_and_sample_data(self):
        demo_user = User.objects.create_user(
            phone="+254720000001", role=User.Role.FARMER
        )
        Farmer.objects.create(
            user=demo_user,
            ward=Ward.objects.get(name="Kisii Central"),
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        call_command("seed_market_demo", verbosity=0)
        call_command("seed_market_demo", verbosity=0)
        self.assertEqual(Crop.objects.count(), 15)
        self.assertEqual(MarketPrice.objects.count(), 450)
        self.assertTrue(MarketPrice.objects.filter(is_sample_data=False).count() == 0)
        self.assertEqual(Buyer.objects.count(), 10)
        self.assertTrue(all(buyer.is_sample_data for buyer in Buyer.objects.all()))
        self.assertEqual(TrainingEvent.objects.count(), 3)
        self.assertTrue(
            all(event.is_sample_data for event in TrainingEvent.objects.all())
        )
        self.assertEqual(
            SellListing.objects.filter(is_sample_data=True).count(), 1
        )
        self.assertEqual(len(HORTICULTURE_CROPS), 15)

    def test_csv_import_creates_and_updates_prices_idempotently(self):
        crop = Crop.objects.create(
            name="Tomato",
            water_needs="Moderate",
            ideal_ph_min=5.5,
            ideal_ph_max=7,
        )
        ward = Ward.objects.get(name="Kisii Central")
        contents = (
            "crop,market_name,ward,price_per_kg,date,is_sample_data\n"
            f"Tomato,Kisii Main Market,Kisii Central,72.50,{timezone.localdate()},true\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "prices.csv"
            csv_path.write_text(contents, encoding="utf-8")
            call_command("import_market_prices", str(csv_path), verbosity=0)
            call_command("import_market_prices", str(csv_path), verbosity=0)
        price = MarketPrice.objects.get(crop=crop, ward=ward)
        self.assertEqual(price.price_per_kg, Decimal("72.50"))
        self.assertTrue(price.is_sample_data)
        self.assertEqual(MarketPrice.objects.count(), 1)

    def test_csv_import_rejects_invalid_rows_without_partial_import(self):
        contents = (
            "crop,market_name,ward,price_per_kg,date\n"
            f"Tomato,Kisii Main Market,Kisii Central,72.50,{timezone.localdate()}\n"
            "Missing crop,Unknown,Kisii Central,20,2026-10-26\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "prices.csv"
            csv_path.write_text(contents, encoding="utf-8")
            with self.assertRaises(CommandError):
                call_command("import_market_prices", str(csv_path), verbosity=0)
        self.assertEqual(MarketPrice.objects.count(), 0)
