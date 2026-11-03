from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Answer, Attempt, District, Option, Participant, Question, Quiz


def make_quiz(status=Quiz.STATUS_DRAFT, duration_minutes=None):
    quiz = Quiz.objects.create(
        title_gu="ટેસ્ટ ક્વિઝ", title_en="Test Quiz", status=status, duration_minutes=duration_minutes
    )
    for order in range(1, 3):
        q = Question.objects.create(quiz=quiz, order=order, text_gu=f"પ્રશ્ન {order}", text_en=f"Question {order}")
        for label in ["A", "B", "C", "D"]:
            Option.objects.create(question=q, label=label, text_gu=label, text_en=label, is_correct=(label == "A"))
    return quiz


class QuizLifecycleTests(TestCase):
    def setUp(self):
        self.district = District.objects.create(name_en="Ahmedabad", name_gu="અમદાવાદ")

    def test_draft_shows_not_open(self):
        quiz = make_quiz(status=Quiz.STATUS_DRAFT)
        resp = self.client.get(reverse("quiz:entry", args=[quiz.code]))
        self.assertContains(resp, "હજુ ઉપલબ્ધ નથી")

    def test_closed_shows_ended(self):
        quiz = make_quiz(status=Quiz.STATUS_CLOSED)
        resp = self.client.get(reverse("quiz:entry", args=[quiz.code]))
        self.assertContains(resp, "આ કસોટી પૂર્ણ થઈ ગઈ છે")

    def test_pre_closed_shows_waiting(self):
        quiz = make_quiz(status=Quiz.STATUS_PRE_CLOSED)
        resp = self.client.get(reverse("quiz:entry", args=[quiz.code]))
        self.assertContains(resp, "ટૂંક સમયમાં શરૂ થશે")

    def test_cannot_open_pre_without_correct_options(self):
        quiz = make_quiz(status=Quiz.STATUS_DRAFT)
        Option.objects.filter(question__quiz=quiz).update(is_correct=False)
        self.assertFalse(quiz.can_open_pre())


class PreTestFlowTests(TestCase):
    def setUp(self):
        self.district = District.objects.create(name_en="Ahmedabad", name_gu="અમદાવાદ")
        self.quiz = make_quiz(status=Quiz.STATUS_PRE_OPEN, duration_minutes=10)

    def _start(self):
        resp = self.client.post(
            reverse("quiz:start_attempt", args=[self.quiz.code]),
            {
                "name": "Teacher One",
                "district": self.district.id,
                "mobile": "9876543210",
                "school_name": "Test School",
                "designation": "Teacher",
            },
        )
        return resp

    def test_details_form_requires_valid_mobile(self):
        resp = self.client.post(
            reverse("quiz:start_attempt", args=[self.quiz.code]),
            {
                "name": "Teacher One",
                "district": self.district.id,
                "mobile": "12345",
                "school_name": "Test School",
                "designation": "Teacher",
            },
        )
        self.assertContains(resp, "valid 10-digit")

    def test_pre_test_never_leaks_correct_answer(self):
        self._start()
        q1 = self.quiz.questions.get(order=1)
        resp = self.client.get(reverse("quiz:question", args=[self.quiz.code, 1]))
        self.assertNotContains(resp, "option-correct")
        self.assertNotContains(resp, "option-wrong")

        resp = self.client.post(
            reverse("quiz:save_answer", args=[self.quiz.code, 1]), {"option": "B"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("is_correct", resp.json())
        self.assertNotIn("correct_label", resp.json())

    def test_pre_test_submit_computes_score_without_revealing(self):
        self._start()
        for q in self.quiz.questions.all():
            self.client.post(reverse("quiz:save_answer", args=[self.quiz.code, q.order]), {"option": "A"})
        resp = self.client.post(reverse("quiz:submit_attempt", args=[self.quiz.code]))
        self.assertContains(resp, "તમારો પ્રતિસાદ નોંધાયો છે")
        attempt = Attempt.objects.get(quiz=self.quiz, phase=Attempt.PHASE_PRE)
        self.assertEqual(attempt.status, Attempt.STATUS_SUBMITTED)
        self.assertEqual(attempt.score, 2)

    def test_one_attempt_per_participant_per_phase(self):
        self._start()
        participant = Participant.objects.get(mobile="9876543210")
        self.assertEqual(Attempt.objects.filter(quiz=self.quiz, participant=participant, phase="pre").count(), 1)
        # second start should not create a duplicate attempt
        self.client.post(reverse("quiz:start_attempt", args=[self.quiz.code]))
        self.assertEqual(Attempt.objects.filter(quiz=self.quiz, participant=participant, phase="pre").count(), 1)


class PostTestFlowTests(TestCase):
    def setUp(self):
        self.district = District.objects.create(name_en="Ahmedabad", name_gu="અમદાવાદ")
        self.quiz = make_quiz(status=Quiz.STATUS_POST_OPEN, duration_minutes=10)
        self.participant = Participant.objects.create(
            name="Teacher Two", mobile="9123456780", district=self.district, school_name="School"
        )
        self.client.cookies["ceequiz_pid"] = self._sign(self.participant)

    def _sign(self, participant):
        from django.conf import settings
        from django.core import signing
        return signing.TimestampSigner(salt="ceequiz.participant").sign(str(participant.pk))

    def test_post_test_reveals_and_locks_answer(self):
        self.client.post(reverse("quiz:start_attempt", args=[self.quiz.code]))
        q1 = self.quiz.questions.get(order=1)

        resp = self.client.post(reverse("quiz:save_answer", args=[self.quiz.code, 1]), {"option": "B"})
        data = resp.json()
        self.assertFalse(data["is_correct"])
        self.assertEqual(data["correct_label"], "A")

        # second attempt to answer the same question is rejected
        resp2 = self.client.post(reverse("quiz:save_answer", args=[self.quiz.code, 1]), {"option": "A"})
        self.assertEqual(resp2.status_code, 403)

        answer = Answer.objects.get(attempt__quiz=self.quiz, question=q1)
        self.assertTrue(answer.locked)

    def test_post_test_without_pre_test_is_flagged(self):
        self.client.post(reverse("quiz:start_attempt", args=[self.quiz.code]))
        attempt = Attempt.objects.get(quiz=self.quiz, phase=Attempt.PHASE_POST)
        self.assertFalse(attempt.had_pre_test)

    def test_thankyou_screen_has_no_score(self):
        self.client.post(reverse("quiz:start_attempt", args=[self.quiz.code]))
        for q in self.quiz.questions.all():
            self.client.post(reverse("quiz:save_answer", args=[self.quiz.code, q.order]), {"option": "A"})
        resp = self.client.post(reverse("quiz:submit_attempt", args=[self.quiz.code]))
        self.assertNotContains(resp, "2/2")
        self.assertNotContains(resp, "score")


class TimerExpiryTests(TestCase):
    def setUp(self):
        self.district = District.objects.create(name_en="Ahmedabad", name_gu="અમદાવાદ")
        self.quiz = make_quiz(status=Quiz.STATUS_PRE_OPEN, duration_minutes=5)
        self.participant = Participant.objects.create(
            name="Teacher Three", mobile="9000000000", district=self.district, school_name="School"
        )
        self.attempt = Attempt.objects.create(
            quiz=self.quiz,
            participant=self.participant,
            phase=Attempt.PHASE_PRE,
            deadline=timezone.now() - timezone.timedelta(seconds=5),
        )

    def test_expired_attempt_auto_submits_on_read(self):
        self.assertTrue(self.attempt.is_expired())
        self.attempt.auto_submit(Attempt.REASON_TIMEOUT)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, Attempt.STATUS_SUBMITTED)
        self.assertEqual(self.attempt.submit_reason, Attempt.REASON_TIMEOUT)


class AdminAccessTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get("/reports/")
        self.assertEqual(resp.status_code, 302)
