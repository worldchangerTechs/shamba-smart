from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from alerts.engine import (
    evaluate_rules,
    evaluate_spray_log,
    priority_for_rule,
    record_rule_feedback,
)
from alerts.models import Alert, AlertDelivery, Rule, RuleWardPriority
from farms.models import Crop, Farm, Planting
from market.models import MarketPrice
from pests.models import PestReport, SprayLog
from weather.models import WeatherSnapshot
from waste.models import WasteLog


class RulesEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=-0.6773, lng=34.7792
        )
        cls.nearby_ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=-0.79, lng=34.72
        )
        cls.officer = User.objects.create_user(
            phone="+254710000001", role=User.Role.OFFICER
        )
        cls.officer.assigned_wards.add(cls.ward)
        cls.farmers = []
        for index in range(4):
            user = User.objects.create_user(
                phone=f"+25472000000{index + 1}",
                role=User.Role.FARMER,
                language=("en", "sw", "guz")[index % 3],
                channel_preference=User.ChannelPreference.SMS,
                consent_sms=True,
            )
            cls.farmers.append(
                Farmer.objects.create(
                    user=user,
                    ward=cls.ward,
                    literacy_level=Farmer.LiteracyLevel.MEDIUM,
                    has_smartphone=False,
                )
            )
        cls.tomato = Crop.objects.create(
            name="Tomato",
            water_needs="Moderate",
            ideal_ph_min=5.5,
            ideal_ph_max=7.0,
        )
        cls.maize = Crop.objects.create(
            name="Maize",
            water_needs="Moderate",
            ideal_ph_min=5.8,
            ideal_ph_max=7.0,
        )
        cls.steep_farm = Farm.objects.create(
            farmer=cls.farmers[0],
            name="Steep farm",
            lat=-0.6773,
            lng=34.7792,
            size_acres=1,
            slope_class=Farm.SlopeClass.STEEP,
            soil_type="loam",
            soil_ph=4.8,
        )
        cls.flat_farm = Farm.objects.create(
            farmer=cls.farmers[1],
            name="Flat farm",
            lat=-0.68,
            lng=34.78,
            size_acres=2,
            slope_class=Farm.SlopeClass.FLAT,
            soil_type="loam",
        )
        cls.tomato_planting = Planting.objects.create(
            farm=cls.steep_farm,
            crop=cls.tomato,
            variety="Roma",
            planted_on=timezone.localdate() - timedelta(days=20),
            expected_harvest=timezone.localdate() + timedelta(days=80),
        )
        cls.maize_planting = Planting.objects.create(
            farm=cls.flat_farm,
            crop=cls.maize,
            variety="Hybrid",
            planted_on=timezone.localdate() - timedelta(days=20),
            expected_harvest=timezone.localdate() + timedelta(days=80),
        )
        rule_defaults = {
            "HEAVY_RAIN_STEEP": ("erosion", Rule.Severity.HIGH, {"rain_forecast_24h": {"over": 25}, "farm": {"slope_class": "STEEP"}}),
            "COOL_WET_TOMATO_BLIGHT": ("pests", Rule.Severity.HIGH, {"temp": {"under": 20}, "humidity": {"over": 85}, "days": 2, "planting": {"crop": "tomato"}}),
            "OUTBREAK_NEARBY": ("pests", Rule.Severity.HIGH, {"confirmed_reports": 3, "days": 7}),
            "SPRAY_LOGGED": ("ppe", Rule.Severity.MEDIUM, {}),
            "LOW_PH": ("soil", Rule.Severity.LOW, {}),
            "DRY_SPELL_MULCH": ("climate", Rule.Severity.MEDIUM, {"days": 7}),
            "PRICE_SPIKE": ("market", Rule.Severity.MEDIUM, {"increase_percent": 20}),
            "WASTE_REMINDER": ("waste", Rule.Severity.LOW, {"days": 7}),
        }
        cls.rules = {}
        for code, (tag, severity, conditions) in rule_defaults.items():
            cls.rules[code], _ = Rule.objects.update_or_create(
                code=code,
                defaults={
                    "problem_tag": tag,
                    "condition_json": conditions,
                    "severity": severity,
                    "message_templates": {},
                    "cooldown_hours": 0 if code in {"SPRAY_LOGGED", "WASTE_REMINDER"} else 24,
                    "active": True,
                },
            )

    def setUp(self):
        self.now = timezone.now()
        self.today = timezone.localdate(self.now)

    def _add_forecast(self, farm, daily_rain=None, min_temp=22, humidity=70):
        daily_rain = daily_rain or [0] * 14
        for day_index in range(14):
            day = self.today + timedelta(days=day_index)
            hourly = [
                {
                    "time": datetime.combine(day, time(hour=hour)).isoformat(),
                    "precipitation": daily_rain[day_index] / 24,
                    "temperature_2m": min_temp,
                    "relative_humidity_2m": humidity,
                }
                for hour in range(24)
            ]
            WeatherSnapshot.objects.create(
                ward=farm.farmer.ward,
                date=day,
                rain_mm=daily_rain[day_index],
                temp_min=min_temp,
                temp_max=min_temp + 5,
                humidity=humidity,
                forecast_json={
                    "is_forecast": True,
                    "hourly": hourly,
                },
            )

    def test_heavy_rain_on_steep_farm_creates_one_erosion_alert(self):
        self._add_forecast(self.steep_farm, [26] + [0] * 13)
        alerts = evaluate_rules(now=self.now)
        erosion = [alert for alert in alerts if alert.rule.code == "HEAVY_RAIN_STEEP"]
        self.assertEqual(len(erosion), 1)
        self.assertEqual(erosion[0].farm, self.steep_farm)
        self.assertIn("erosion", erosion[0].rule.problem_tag)
        self.assertEqual(erosion[0].severity, Rule.Severity.HIGH)
        evaluate_rules(now=self.now + timedelta(minutes=1))
        self.assertEqual(Alert.objects.filter(rule=self.rules["HEAVY_RAIN_STEEP"]).count(), 1)

    def test_cool_wet_tomatoes_for_two_days_create_blight_warning(self):
        self._add_forecast(
            self.steep_farm,
            daily_rain=[0.5, 0.5] + [0] * 12,
            min_temp=17,
            humidity=90,
        )
        alerts = evaluate_rules(now=self.now)
        blight = next(alert for alert in alerts if alert.rule.code == "COOL_WET_TOMATO_BLIGHT")
        self.assertEqual(blight.farm, self.steep_farm)
        self.assertEqual(blight.rule.problem_tag, "pests")

    def test_three_confirmed_same_pest_reports_trigger_ward_alert(self):
        for index in range(3):
            PestReport.objects.create(
                farmer=self.farmers[index],
                farm=self.steep_farm if index == 0 else self.flat_farm,
                crop=self.tomato,
                description="",
                lat=self.ward.lat,
                lng=self.ward.lng,
                ward=self.ward,
                status=PestReport.Status.CONFIRMED,
                pest_name="Aphids",
            )
        evaluate_rules(now=self.now)
        outbreak_alerts = list(
            Alert.objects.filter(rule=self.rules["OUTBREAK_NEARBY"])
        )
        self.assertEqual(len(outbreak_alerts), 1)
        self.assertTrue(all(alert.farmer.ward == self.ward for alert in outbreak_alerts))
        self.assertTrue(all("3 confirmed" in alert.body_by_language["en"] for alert in outbreak_alerts))

    def test_spray_log_creates_ppe_reentry_and_preharvest_alert(self):
        spray = SprayLog.objects.create(
            farm=self.steep_farm,
            product_name="Safe Crop",
            active_ingredient="Example active",
            sprayed_at=self.now,
            ppe_checked=False,
            reentry_hours=24,
            pre_harvest_days=7,
        )
        alert = evaluate_spray_log(spray)[0]
        self.assertEqual(alert.rule.code, "SPRAY_LOGGED")
        self.assertEqual(alert.rule.problem_tag, "ppe")
        self.assertIn("24 hours", alert.body_by_language["en"])
        self.assertIn("7 days", alert.body_by_language["en"])

    def test_spray_log_creation_queues_the_alert_task(self):
        from alerts.tasks import alert_for_spray_log

        with patch.object(alert_for_spray_log, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                spray = SprayLog.objects.create(
                    farm=self.steep_farm,
                    product_name="Safety product",
                    active_ingredient="Example active",
                    sprayed_at=self.now,
                    ppe_checked=False,
                    reentry_hours=8,
                    pre_harvest_days=3,
                )
        delay.assert_called_once_with(spray.pk)

    def test_low_ph_creates_crop_specific_lime_advice(self):
        alerts = evaluate_rules(now=self.now)
        low_ph = next(alert for alert in alerts if alert.rule.code == "LOW_PH")
        self.assertEqual(low_ph.farm, self.steep_farm)
        self.assertIn("Tomato", low_ph.body_by_language["en"])

    def test_seven_day_dry_spell_creates_mulch_and_irrigation_tip(self):
        self._add_forecast(self.steep_farm)
        alerts = evaluate_rules(now=self.now)
        dry = next(alert for alert in alerts if alert.rule.code == "DRY_SPELL_MULCH")
        self.assertIn("Mulch", dry.body_by_language["en"])
        self.assertIn("irrigate", dry.body_by_language["en"])

    def test_nearest_market_price_spike_compares_with_prior_four_weeks(self):
        today = self.today
        for index in range(4):
            MarketPrice.objects.create(
                crop=self.maize,
                market_name="Kisii market",
                ward=self.ward,
                price_per_kg=Decimal("50.00"),
                date=today - timedelta(days=7 * (index + 1)),
            )
        MarketPrice.objects.create(
            crop=self.maize,
            market_name="Kisii market",
            ward=self.ward,
            price_per_kg=Decimal("65.00"),
            date=today,
        )
        MarketPrice.objects.create(
            crop=self.maize,
            market_name="Bobasi market",
            ward=self.nearby_ward,
            price_per_kg=Decimal("45.00"),
            date=today,
        )
        alerts = evaluate_rules(now=self.now)
        price_alert = next(alert for alert in alerts if alert.rule.code == "PRICE_SPIKE")
        self.assertEqual(price_alert.farm, self.flat_farm)
        self.assertIn("Kisii market", price_alert.body_by_language["en"])

    def test_seven_day_spray_waste_reminder_and_linked_disposal_deduplication(self):
        spray = SprayLog.objects.create(
            farm=self.steep_farm,
            product_name="Safe Crop",
            active_ingredient="Example active",
            sprayed_at=self.now - timedelta(days=8),
            ppe_checked=True,
            reentry_hours=12,
            pre_harvest_days=5,
        )
        alerts = evaluate_rules(now=self.now)
        waste = next(alert for alert in alerts if alert.rule.code == "WASTE_REMINDER")
        self.assertIn("Triple-rinse", waste.body_by_language["en"])
        WasteLog.objects.create(
            farmer=self.farmers[0],
            spray_log=spray,
            waste_type=WasteLog.WasteType.CHEMICAL_CONTAINER,
            action="Triple-rinsed and dropped off",
        )
        spray_2 = SprayLog.objects.create(
            farm=self.steep_farm,
            product_name="Second product",
            active_ingredient="Another active",
            sprayed_at=self.now - timedelta(days=8),
            ppe_checked=True,
            reentry_hours=12,
            pre_harvest_days=5,
        )
        alerts = evaluate_rules(now=self.now + timedelta(minutes=1))
        reminders = [alert for alert in alerts if alert.rule.code == "WASTE_REMINDER"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("Second product", reminders[0].body_by_language["en"])

    def test_feedback_after_repeated_not_relevant_votes_reduces_rule_ward_priority(self):
        rule = self.rules["DRY_SPELL_MULCH"]
        deliveries = []
        for index in range(3):
            alert = Alert.objects.create(
                farmer=self.farmers[index],
                farm=self.steep_farm,
                rule=rule,
                severity=rule.severity,
                title="Dry",
                body_by_language={"en": "Dry"},
                source_key=f"dry:{index}",
            )
            deliveries.append(
                AlertDelivery.objects.create(
                    alert=alert,
                    channel=AlertDelivery.Channel.SMS,
                    delivered=True,
                    sent_at=self.now,
                    feedback=AlertDelivery.Feedback.NOT_RELEVANT,
                )
            )
        record_rule_feedback(deliveries[-1])
        priority = RuleWardPriority.objects.get(rule=rule, ward=self.ward)
        self.assertEqual(priority.priority, 90)
        self.assertEqual(priority_for_rule(rule, self.ward), 90)

    def test_alert_rules_are_scheduled_every_three_hours(self):
        from django.conf import settings

        schedule = settings.CELERY_BEAT_SCHEDULE[
            "evaluate-alert-rules-every-three-hours"
        ]["schedule"]
        self.assertEqual(schedule.run_every, timedelta(hours=3))

    def test_feedback_endpoint_only_allows_recipient_and_valid_feedback(self):
        alert = Alert.objects.create(
            farmer=self.farmers[0],
            farm=self.steep_farm,
            rule=self.rules["LOW_PH"],
            severity=Rule.Severity.LOW,
            title="Soil",
            body_by_language={"en": "Soil"},
        )
        delivery = AlertDelivery.objects.create(
            alert=alert,
            channel=AlertDelivery.Channel.SMS,
            delivered=True,
            sent_at=self.now,
        )
        client = APIClient()
        client.force_authenticate(user=self.farmers[0].user)
        response = client.post(
            f"/api/alert-deliveries/{delivery.pk}/feedback/",
            {"feedback": "HELPFUL"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["feedback"], "HELPFUL")

        client.force_authenticate(user=self.farmers[1].user)
        response = client.post(
            f"/api/alert-deliveries/{delivery.pk}/feedback/",
            {"feedback": "NOT_RELEVANT"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class AlertDraftTests(TestCase):
    def setUp(self):
        ward = Ward.objects.create(
            name="Marani", sub_county="Marani", lat=-0.56, lng=34.8
        )
        self.user = User.objects.create_user(
            phone="+254720010001",
            role=User.Role.FARMER,
            language="sw",
            channel_preference=User.ChannelPreference.SMS,
            consent_sms=True,
        )
        self.farmer = Farmer.objects.create(
            user=self.user,
            ward=ward,
            literacy_level=Farmer.LiteracyLevel.LOW,
            has_smartphone=False,
        )
        self.rule = Rule.objects.create(
            code="TEST_MESSENGER",
            problem_tag="test",
            severity=Rule.Severity.MEDIUM,
            message_templates={},
        )

    def _alert(self, severity=Rule.Severity.MEDIUM, suffix=""):
        return Alert.objects.create(
            farmer=self.farmer,
            rule=self.rule,
            severity=severity,
            title=f"Test {suffix}",
            body_by_language={
                "en": "English",
                "sw": "Ujumbe wa Kiswahili " + ("x" * 180),
                "guz": "Gusii",
            },
        )

    def test_alert_is_a_draft_until_a_manual_warning_batch_is_sent(self):
        alert = self._alert()
        self.assertEqual(alert.status, Alert.Status.OPEN)
        self.assertFalse(alert.deliveries.exists())
