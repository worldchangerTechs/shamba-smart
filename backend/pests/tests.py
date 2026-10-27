from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from alerts.models import Alert, Rule
from farms.models import Crop, Farm, Planting
from pests.models import Outbreak, PestKnowledge, PestReport, SprayLog


def uploaded_test_photo():
    stream = BytesIO()
    Image.new("RGB", (2, 2), color="green").save(stream, format="JPEG")
    return SimpleUploadedFile(
        "leaf.jpg", stream.getvalue(), content_type="image/jpeg"
    )


class PestReportApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=0, lng=0
        )
        cls.other_ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=0, lng=0.04
        )
        cls.crop = Crop.objects.create(
            name="Tomato",
            water_needs="Moderate",
            ideal_ph_min=5.5,
            ideal_ph_max=7,
        )
        cls.farmers = []
        for index in range(4):
            user = User.objects.create_user(
                phone=f"+25472003000{index}",
                role=User.Role.FARMER,
                language="en",
            )
            farmer = Farmer.objects.create(
                user=user,
                ward=cls.ward,
                literacy_level=Farmer.LiteracyLevel.MEDIUM,
                has_smartphone=True,
            )
            cls.farmers.append(farmer)
        cls.own_farm = Farm.objects.create(
            farmer=cls.farmers[0],
            name="Reporting farmer farm",
            lat=0,
            lng=0,
            size_acres=1,
            slope_class=Farm.SlopeClass.GENTLE,
            soil_type="loam",
        )
        cls.officer = User.objects.create_user(
            phone="+254710030001", role=User.Role.OFFICER
        )
        cls.officer.assigned_wards.add(cls.ward)
        cls.nearby_farm = Farm.objects.create(
            farmer=cls.farmers[2],
            name="Nearby tomato farm",
            lat=0.01,
            lng=0.01,
            size_acres=1,
            slope_class=Farm.SlopeClass.GENTLE,
            soil_type="loam",
        )
        Planting.objects.create(
            farm=cls.nearby_farm,
            crop=cls.crop,
            variety="Roma",
            planted_on=timezone.localdate() - timedelta(days=20),
            expected_harvest=timezone.localdate() + timedelta(days=60),
        )
        cls.far_farm = Farm.objects.create(
            farmer=cls.farmers[3],
            name="Distant tomato farm",
            lat=0.09,
            lng=0.09,
            size_acres=1,
            slope_class=Farm.SlopeClass.FLAT,
            soil_type="loam",
        )
        Planting.objects.create(
            farm=cls.far_farm,
            crop=cls.crop,
            variety="Roma",
            planted_on=timezone.localdate() - timedelta(days=20),
            expected_harvest=timezone.localdate() + timedelta(days=60),
        )

    def setUp(self):
        self.client = APIClient()

    def test_farmer_submits_photo_symptoms_crop_and_farm_location(self):
        farmer = self.farmers[0]
        self.client.force_authenticate(farmer.user)
        response = self.client.post(
            "/api/pest-reports/",
            {
                "farm": self.own_farm.pk,
                "crop": self.crop.pk,
                "symptoms": "Holes and fresh waste in leaves",
                "description": "Damage appeared this morning",
                "photo": uploaded_test_photo(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        report = PestReport.objects.get(pk=response.data["id"])
        self.assertEqual(report.farmer_id, farmer.pk)
        self.assertEqual(report.ward_id, farmer.ward_id)
        self.assertEqual(report.status, PestReport.Status.PENDING)
        self.assertEqual(report.crop_id, self.crop.pk)
        self.assertEqual((report.lat, report.lng), (self.own_farm.lat, self.own_farm.lng))
        self.assertTrue(report.photo.name)

    def test_report_requires_photo_and_location_and_cannot_assign_other_farm(self):
        self.client.force_authenticate(self.farmers[0].user)
        base = {"crop": self.crop.pk}
        response = self.client.post("/api/pest-reports/", base, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("photo", response.data)

        payload = {
            "crop": self.crop.pk,
            "photo": uploaded_test_photo(),
        }
        response = self.client.post(
            "/api/pest-reports/", payload, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("location", response.data)

        payload = {
            "farm": self.nearby_farm.pk,
            "crop": self.crop.pk,
            "photo": uploaded_test_photo(),
        }
        response = self.client.post(
            "/api/pest-reports/", payload, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("farm", response.data)

    def test_officer_verification_queue_and_request_for_more_info(self):
        report = PestReport.objects.create(
            farmer=self.farmers[0],
            crop=self.crop,
            ward=self.ward,
            photo=uploaded_test_photo(),
            lat=0,
            lng=0,
        )
        self.client.force_authenticate(self.officer)
        response = self.client.get("/api/pest-reports/verification-queue/")
        self.assertEqual(response.status_code, 200, response.data)
        item = response.data["results"][0] if "results" in response.data else response.data[0]
        self.assertEqual(item["id"], report.pk)
        self.assertTrue(item["photo"].endswith(report.photo.name))

        response = self.client.patch(
            f"/api/pest-reports/{report.pk}/verify/",
            {"decision": "ASK_FOR_INFO", "note": "Please add a close-up photo."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        report.refresh_from_db()
        self.assertEqual(report.status, PestReport.Status.NEEDS_INFO)
        self.assertEqual(report.verification_note, "Please add a close-up photo.")
        self.assertEqual(report.verified_by_id, self.officer.pk)
        response = self.client.patch(
            f"/api/pest-reports/{report.pk}/verify/",
            {"decision": "REJECT", "note": "No pest symptoms are visible."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        report.refresh_from_db()
        self.assertEqual(report.status, PestReport.Status.REJECTED)
        self.assertEqual(report.verification_note, "No pest symptoms are visible.")

    def test_confirmed_reports_update_ward_outbreak_and_alert_only_nearby_crop_growers(self):
        reports = []
        for index in range(3):
            reports.append(
                PestReport.objects.create(
                    farmer=self.farmers[index],
                    crop=self.crop,
                    ward=self.ward,
                    photo=uploaded_test_photo(),
                    lat=0,
                    lng=0,
                )
            )
        self.client.force_authenticate(self.officer)
        for report in reports:
            response = self.client.patch(
                f"/api/pest-reports/{report.pk}/verify/",
                {"decision": "CONFIRM", "pest_name": "tomato_leafminer"},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)

        outbreak = Outbreak.objects.get(ward=self.ward, pest_name="tomato_leafminer")
        self.assertEqual(outbreak.confirmed_count, 3)
        self.assertEqual(outbreak.level, Outbreak.Level.MEDIUM)
        rule = Rule.objects.get(code="OUTBREAK_NEARBY")
        alerts = Alert.objects.filter(rule=rule)
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.get().farmer_id, self.farmers[2].pk)
        self.assertEqual(alerts.get().farm_id, self.nearby_farm.pk)
        self.assertEqual(alerts.get().severity, Rule.Severity.HIGH)

    def test_verify_rejects_unknown_pest_and_officer_from_other_ward(self):
        report = PestReport.objects.create(
            farmer=self.farmers[0],
            crop=self.crop,
            ward=self.ward,
            photo=uploaded_test_photo(),
            lat=0,
            lng=0,
        )
        self.client.force_authenticate(self.officer)
        response = self.client.patch(
            f"/api/pest-reports/{report.pk}/verify/",
            {"decision": "CONFIRM", "pest_name": "unknown"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        other_officer = User.objects.create_user(
            phone="+254710030002", role=User.Role.OFFICER
        )
        other_officer.assigned_wards.add(self.other_ward)
        self.client.force_authenticate(other_officer)
        response = self.client.patch(
            f"/api/pest-reports/{report.pk}/verify/",
            {"decision": "REJECT", "note": "Not a pest report."},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class PestKnowledgeAndPublicApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_knowledge_base_has_safe_actions_ipm_and_officer_guidance(self):
        response = self.client.get("/api/pests/knowledge/?language=sw")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["guide_not_diagnosis"])
        self.assertEqual(len(response.data["results"]), 6)
        late_blight = next(
            item for item in response.data["results"] if item["pest_name"] == "late_blight"
        )
        self.assertTrue(late_blight["symptoms"])
        self.assertTrue(late_blight["safe_first_actions"])
        self.assertTrue(late_blight["integrated_pest_management"])
        self.assertTrue(late_blight["when_to_call_an_officer"])

    def test_symptom_icon_helper_returns_confidence_and_non_diagnosis_notice(self):
        response = self.client.post(
            "/api/pests/identify/",
            {
                "symptom_icons": [
                    "leaf_holes",
                    "frass",
                    "aphid_clusters",
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("not a diagnosis", response.data["notice"])
        self.assertEqual(response.data["results"][0]["pest_name"], "fall_armyworm")
        self.assertEqual(response.data["results"][0]["confidence"], "More likely")
        self.assertTrue(response.data["results"][0]["guide_not_diagnosis"])

    def test_pest_helper_requires_three_distinct_symptom_icons(self):
        response = self.client.post(
            "/api/pests/identify/",
            {"symptom_icons": ["leaf_holes", "leaf_holes", "frass"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_public_stats_exposes_only_weekly_report_and_ward_counters(self):
        ward = Ward.objects.create(
            name="Marani", sub_county="Marani", lat=-0.5, lng=34.8
        )
        user = User.objects.create_user(
            phone="+254720030099", role=User.Role.FARMER
        )
        farmer = Farmer.objects.create(
            user=user,
            ward=ward,
            literacy_level=Farmer.LiteracyLevel.LOW,
        )
        crop = Crop.objects.create(
            name="Maize", water_needs="Moderate", ideal_ph_min=5.5, ideal_ph_max=7
        )
        PestReport.objects.create(
            farmer=farmer,
            crop=crop,
            ward=ward,
            lat=ward.lat,
            lng=ward.lng,
            status=PestReport.Status.PENDING,
        )
        Outbreak.objects.create(
            ward=ward,
            pest_name="fall_armyworm",
            crop=crop,
            started_at=timezone.now(),
            confirmed_count=3,
            level=Outbreak.Level.MEDIUM,
        )
        response = self.client.get("/api/pests/stats/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data,
            {"reports_this_week": 1, "wards_on_alert": 1},
        )

    def test_outbreak_endpoint_returns_scoped_geojson(self):
        ward = Ward.objects.create(
            name="Nyamache", sub_county="Nyamache", lat=-0.7, lng=34.6
        )
        crop = Crop.objects.create(
            name="Beans", water_needs="Low", ideal_ph_min=5.5, ideal_ph_max=7
        )
        Outbreak.objects.create(
            ward=ward,
            crop=crop,
            pest_name="aphids",
            started_at=timezone.now(),
            confirmed_count=4,
            level=Outbreak.Level.MEDIUM,
        )
        user = User.objects.create_user(
            phone="+254720030098", role=User.Role.FARMER
        )
        Farmer.objects.create(
            user=user,
            ward=ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        self.client.force_authenticate(user)
        response = self.client.get("/api/pests/outbreaks/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["type"], "FeatureCollection")
        feature = response.data["features"][0]
        self.assertEqual(feature["geometry"]["type"], "Point")
        self.assertEqual(feature["geometry"]["coordinates"], [ward.lng, ward.lat])
