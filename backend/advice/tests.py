from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from advice.models import AdviceContent, PpeSupplier
from farms.models import Crop, Farm
from pests.models import SprayLog
from weather.models import WeatherSnapshot
from waste.models import DisposalPoint


class AdviceServicesApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=-0.6773, lng=34.7792
        )
        cls.user = User.objects.create_user(
            phone="+254720009901",
            role=User.Role.FARMER,
            language="sw",
            channel_preference=User.ChannelPreference.APP,
        )
        cls.farmer = Farmer.objects.create(
            user=cls.user,
            ward=cls.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
            has_smartphone=True,
        )
        cls.crop = Crop.objects.create(
            name="Tomato",
            water_needs="Moderate",
            ideal_ph_min=5.5,
            ideal_ph_max=7,
        )
        cls.farm = Farm.objects.create(
            farmer=cls.farmer,
            name="Home farm",
            lat=-0.6773,
            lng=34.7792,
            size_acres=Decimal("1.00"),
            slope_class=Farm.SlopeClass.STEEP,
            soil_type="loam",
            soil_ph=4.9,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_seed_contains_twenty_database_advice_cards(self):
        self.assertEqual(AdviceContent.objects.filter(active=True).count(), 20)
        self.assertTrue(
            AdviceContent.objects.filter(
                code="LIME_LOW_PH",
                title_en__gt="",
                title_sw__gt="",
                body_en__gt="",
                body_sw__gt="",
            ).exists()
        )

    def test_udongo_doctor_ranks_costed_tasks_and_warns_against_overuse(self):
        response = self.client.post(
            "/api/advice/udongo-doctor/",
            {"crop": "Tomato", "soil_ph": 4.8},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        codes = [task["code"] for task in response.data["tasks"]]
        self.assertEqual(codes[:3], ["LIME_LOW_PH", "COMPOST", "TOP_DRESS"])
        lime = response.data["tasks"][0]
        self.assertEqual(lime["cost_kes_per_acre"], {"min": 2500, "max": 7000})
        self.assertIn("mbolea", response.data["warning"]["body"].casefold())
        self.assertIn("udongo", response.data["summary"].casefold())

    def test_udongo_doctor_accepts_six_answers_and_rejects_partial_quiz(self):
        quiz = {
            "leaf_colour": "yellow",
            "soil_colour": "pale",
            "past_yields": "falling",
            "rain_washing": "yes",
            "mulch_use": "no",
            "manure_use": "no",
        }
        response = self.client.post(
            "/api/advice/udongo-doctor/",
            {"crop": "Tomato", "quiz": quiz},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        codes = [task["code"] for task in response.data["tasks"]]
        self.assertIn("COMPOST", codes)
        self.assertIn("MANURE", codes)
        self.assertEqual(response.data["visual_fertility_signals"], 6)

        response = self.client.post(
            "/api/advice/udongo-doctor/",
            {"crop": "Tomato", "quiz": {"leaf_colour": "yellow"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_mteremko_guard_scores_risk_and_returns_cost_ranked_controls_and_calendar(self):
        today = timezone.localdate()
        WeatherSnapshot.objects.create(
            ward=self.ward,
            date=today,
            rain_mm=40,
            temp_min=15,
            temp_max=22,
            humidity=90,
            forecast_json={"is_forecast": True},
        )
        response = self.client.post(
            "/api/advice/mteremko-guard/",
            {
                "farm_id": self.farm.pk,
                "ground_cover_percent": 0,
                "tillage": "upslope",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreaterEqual(response.data["risk_score"], 70)
        self.assertLessEqual(response.data["risk_score"], 100)
        controls = response.data["controls"]
        costs = [item["cost_kes_per_acre"]["min"] for item in controls]
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(len(response.data["seasonal_erosion_calendar"]), 4)

    def test_ppe_gap_finder_lists_cheapest_missing_gear_and_nearest_supplier(self):
        nearby = PpeSupplier.objects.create(
            name="Kisii Agro",
            supplier_type=PpeSupplier.SupplierType.AGRO_DEALER,
            ward=self.ward,
            lat=-0.68,
            lng=34.78,
            contact="0700000000",
            item_prices_kes={"mask": 250, "gloves": 300, "boots": 1200},
        )
        PpeSupplier.objects.create(
            name="Far Cooperative",
            supplier_type=PpeSupplier.SupplierType.COOPERATIVE,
            ward=self.ward,
            lat=-0.9,
            lng=34.9,
            item_prices_kes={"mask": 100, "overall": 800, "goggles": 400},
        )
        response = self.client.post(
            "/api/advice/ppe-gap-finder/",
            {"farm_id": self.farm.pk, "owned_items": ["boots"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        prices = [
            item["lowest_price_kes"]
            for item in response.data["missing_items"]
            if item["lowest_price_kes"] is not None
        ]
        self.assertEqual(prices, sorted(prices))
        mask = next(
            item for item in response.data["missing_items"] if item["code"] == "mask"
        )
        self.assertEqual(mask["lowest_price_kes"], 100)
        self.assertEqual(mask["supplier"]["name"], "Far Cooperative")
        self.assertEqual(response.data["nearest_supplier"]["id"], nearby.pk)

    def test_spray_log_returns_protection_and_harvest_waits(self):
        sprayed_at = timezone.now()
        response = self.client.post(
            "/api/spray-logs/",
            {
                "farm": self.farm.pk,
                "product_name": "Crop Guard",
                "active_ingredient": "Example",
                "sprayed_at": sprayed_at.isoformat(),
                "ppe_checked": False,
                "reentry_hours": 12,
                "pre_harvest_days": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["checklist"]), 5)
        self.assertFalse(any(item["checked"] for item in response.data["checklist"]))
        self.assertGreater(response.data["reentry_remaining_seconds"], 0)
        self.assertEqual(response.data["pre_harvest_interval_days"], 5)
        self.assertTrue(response.data["harvest_locked"])
        self.assertEqual(
            SprayLog.objects.get(pk=response.data["spray_log"]["id"]).farm_id,
            self.farm.pk,
        )

    def test_taka_loop_finds_nearest_dropoff_and_tracks_clean_farm_score(self):
        near = DisposalPoint.objects.create(
            name="Kisii collection point",
            type="Chemical containers",
            lat=-0.68,
            lng=34.78,
            ward=self.ward,
        )
        DisposalPoint.objects.create(
            name="Distant collection point",
            type="Chemical containers",
            lat=-1.2,
            lng=35.1,
            ward=self.ward,
        )
        response = self.client.post(
            "/api/waste-logs/",
            {"waste_type": "CHEMICAL_CONTAINER", "action": "Triple-rinsed"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["clean_farm"]["waste_action_count"], 1)
        self.assertEqual(response.data["clean_farm"]["score"], 10)

        response = self.client.get(
            "/api/advice/taka-loop/?waste_type=CHEMICAL_CONTAINER"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["nearest_disposal_point"]["id"], near.pk
        )
        self.assertIn("mara tatu", response.data["recipe"]["body"])
