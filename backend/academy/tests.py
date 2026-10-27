from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Farmer, User, Ward
from academy.models import (
    Badge,
    FrequentlyAskedQuestion,
    Lesson,
    LessonProgress,
    OfficerQuestion,
)
from academy.tasks import send_weekly_tips


class AcademyApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ward = Ward.objects.create(
            name="Kisii Central", sub_county="Kisii Central", lat=-0.6773, lng=34.7792
        )
        cls.other_ward = Ward.objects.create(
            name="Bobasi", sub_county="Bobasi", lat=-0.79, lng=34.72
        )
        cls.user = User.objects.create_user(
            phone="+254720050001", role=User.Role.FARMER, language="en"
        )
        cls.farmer = Farmer.objects.create(
            user=cls.user,
            ward=cls.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        cls.officer = User.objects.create_user(
            phone="+254710050001", role=User.Role.OFFICER
        )
        cls.officer.assigned_wards.add(cls.ward)
        cls.other_officer = User.objects.create_user(
            phone="+254710050002", role=User.Role.OFFICER
        )
        cls.other_officer.assigned_wards.add(cls.other_ward)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_seed_has_sixteen_lessons_two_per_problem_tag(self):
        lessons = Lesson.objects.filter(active=True)
        self.assertEqual(lessons.count(), 16)
        for tag, _label in Lesson.ProblemTag.choices:
            self.assertEqual(lessons.filter(problem_tag=tag).count(), 2)
        for lesson in lessons:
            self.assertLessEqual(lesson.duration_sec, 120)
            for language in ("en", "sw"):
                self.assertEqual(len(lesson.body_by_language[language]), 5)
                self.assertEqual(len(lesson.quiz_by_language[language]), 3)

    def test_lesson_detail_localizes_content_and_hides_quiz_answers(self):
        self.user.language = User.Language.SW
        self.user.save(update_fields=("language",))
        lesson = Lesson.objects.filter(problem_tag=Lesson.ProblemTag.SOIL).first()
        response = self.client.get(f"/api/lessons/{lesson.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["title"], lesson.title_by_language["sw"])
        self.assertEqual(len(response.data["steps"]), 5)
        self.assertEqual(len(response.data["quiz"]), 3)
        self.assertNotIn("answer_index", response.data["quiz"][0])
        self.assertEqual(set(response.data["audio_by_language"]), {"en", "sw", "guz"})

    def test_farmer_completes_quiz_and_earns_soil_hero_after_two_lessons(self):
        lessons = list(
            Lesson.objects.filter(problem_tag=Lesson.ProblemTag.SOIL).order_by("pk")
        )
        for lesson in lessons:
            response = self.client.post(
                "/api/lesson-progress/",
                {
                    "lesson": lesson.pk,
                    "completed_steps": 5,
                    "quiz_answers": [1, 2, 0],
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertTrue(response.data["completed"])
            self.assertEqual(response.data["quiz_score"], 3)
        self.assertEqual(
            LessonProgress.objects.filter(farmer=self.farmer, completed=True).count(),
            2,
        )
        badge = Badge.objects.get(farmer=self.farmer, code=Badge.BadgeCode.SOIL_HERO)
        self.assertEqual(badge.name, "Soil Hero")

    def test_incorrect_quiz_does_not_complete_lesson(self):
        lesson = Lesson.objects.filter(problem_tag=Lesson.ProblemTag.PPE).first()
        response = self.client.post(
            "/api/lesson-progress/",
            {"lesson": lesson.pk, "quiz_answers": [0, 0, 1]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(response.data["completed"])
        self.assertEqual(response.data["quiz_score"], 0)

    def test_farmer_cannot_edit_another_farmers_progress_or_award_badges(self):
        lesson = Lesson.objects.first()
        other_user = User.objects.create_user(
            phone="+254720050002", role=User.Role.FARMER
        )
        other_farmer = Farmer.objects.create(
            user=other_user,
            ward=self.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        progress = LessonProgress.objects.create(
            farmer=other_farmer, lesson=lesson
        )
        response = self.client.patch(
            f"/api/lesson-progress/{progress.pk}/",
            {"completed_steps": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/api/badges/",
            {"farmer": self.farmer.pk, "code": "SOIL_HERO", "name": "Soil Hero"},
            format="json",
        )
        self.assertEqual(response.status_code, 405)

    def test_farmer_asks_question_and_officer_answer_becomes_searchable_faq(self):
        response = self.client.post(
            "/api/officer-questions/",
            {"question": "Why are my tomato leaves turning yellow?"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        question_id = response.data["id"]
        self.assertEqual(response.data["status"], OfficerQuestion.Status.OPEN)

        self.client.force_authenticate(self.officer)
        response = self.client.get("/api/officer-questions/queue/")
        self.assertEqual(response.status_code, 200, response.data)
        queue = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(queue[0]["id"], question_id)

        response = self.client.post(
            f"/api/officer-questions/{question_id}/answer/",
            {
                "answer": "Check soil moisture and ask for a soil test before adding fertiliser.",
                "language": "en",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], OfficerQuestion.Status.ANSWERED)
        faq = FrequentlyAskedQuestion.objects.get(source_question_id=question_id)
        self.assertIn("soil test", faq.search_terms)

        self.client.force_authenticate(self.user)
        response = self.client.get("/api/faqs/?q=soil%20test&language=en")
        self.assertEqual(response.status_code, 200, response.data)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], faq.pk)

    def test_question_requires_text_or_voice_and_officers_are_ward_scoped(self):
        response = self.client.post(
            "/api/officer-questions/", {"question": "", "voice_note": None}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        question = OfficerQuestion.objects.create(
            farmer=self.farmer,
            ward=self.ward,
            question="How do I conserve soil?",
        )
        self.client.force_authenticate(self.other_officer)
        response = self.client.post(
            f"/api/officer-questions/{question.pk}/answer/",
            {"answer": "Plant across the slope.", "language": "en"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_weekly_tip_job_creates_draft_alerts_without_sending_sms(self):
        opted_in = User.objects.create_user(
            phone="+254720050003",
            role=User.Role.FARMER,
            language="sw",
            consent_sms=True,
        )
        Farmer.objects.create(
            user=opted_in,
            ward=self.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        not_opted_in = User.objects.create_user(
            phone="+254720050004",
            role=User.Role.FARMER,
            consent_sms=False,
        )
        Farmer.objects.create(
            user=not_opted_in,
            ward=self.ward,
            literacy_level=Farmer.LiteracyLevel.MEDIUM,
        )
        first = send_weekly_tips.run()
        second = send_weekly_tips.run()
        self.assertGreater(first["alerts_created"], 0)
        self.assertEqual(second["alerts_created"], 0)
        self.assertEqual(first["sent"], 0)
        self.assertFalse(
            self.farmer.alerts.filter(title="Shamba Tip of the Week")
            .first()
            .deliveries.exists()
        )

    def test_weekly_tip_schedule_is_monday_nairobi_time(self):
        from django.conf import settings

        schedule = settings.CELERY_BEAT_SCHEDULE["create-weekly-farmer-tip-drafts"][
            "schedule"
        ]
        self.assertEqual(schedule.hour, {9})
        self.assertEqual(schedule.minute, {0})
        self.assertEqual(settings.CELERY_TIMEZONE, "Africa/Nairobi")
