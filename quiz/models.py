import random
import string

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def generate_quiz_code():
    alphabet = string.ascii_lowercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=8))
        if not Quiz.objects.filter(code=code).exists():
            return code


class District(models.Model):
    name_en = models.CharField(max_length=100)
    name_gu = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_en"]

    def __str__(self):
        return self.name_en


class School(models.Model):
    name = models.CharField(max_length=255)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    udise_code = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Quiz(models.Model):
    AUDIENCE_TEACHER = "teacher"
    AUDIENCE_STUDENT = "student"
    AUDIENCE_CHOICES = [
        (AUDIENCE_TEACHER, "Teacher"),
        (AUDIENCE_STUDENT, "Student"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PRE_OPEN = "pre_open"
    STATUS_PRE_CLOSED = "pre_closed"
    STATUS_POST_OPEN = "post_open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PRE_OPEN, "Pre-test open"),
        (STATUS_PRE_CLOSED, "Pre-test closed"),
        (STATUS_POST_OPEN, "Post-test open"),
        (STATUS_CLOSED, "Closed"),
    ]

    title_gu = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)
    code = models.CharField(max_length=8, unique=True, default=generate_quiz_code, editable=False)
    event_name = models.CharField(max_length=255, blank=True)
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default=AUDIENCE_TEACHER)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Blank = untimed")
    phase_closes_at = models.DateTimeField(null=True, blank=True, help_text="Auto-close the current open phase at this time")
    instructions_gu = models.TextField(blank=True)
    instructions_en = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return self.title_en or self.title_gu

    def questions_missing_correct_option(self):
        return self.questions.exclude(options__is_correct=True).exists()

    def can_open_pre(self):
        return self.status == self.STATUS_DRAFT and not self.questions_missing_correct_option()

    def can_close_pre(self):
        return self.status == self.STATUS_PRE_OPEN

    def can_open_post(self):
        return self.status in (self.STATUS_PRE_CLOSED, self.STATUS_DRAFT) and not self.questions_missing_correct_option()

    def can_close(self):
        return self.status in (self.STATUS_PRE_OPEN, self.STATUS_PRE_CLOSED, self.STATUS_POST_OPEN)

    def current_phase(self):
        if self.status == self.STATUS_PRE_OPEN:
            return Attempt.PHASE_PRE
        if self.status == self.STATUS_POST_OPEN:
            return Attempt.PHASE_POST
        return None


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField()
    text_gu = models.TextField()
    text_en = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("quiz", "order")]

    def __str__(self):
        return f"{self.order}. {self.text_en or self.text_gu}"

    def text(self, lang):
        if lang == "en" and self.text_en:
            return self.text_en
        return self.text_gu


class Option(models.Model):
    LABEL_CHOICES = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=1, choices=LABEL_CHOICES)
    text_gu = models.CharField(max_length=500)
    text_en = models.CharField(max_length=500, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["label"]
        unique_together = [("question", "label")]

    def __str__(self):
        return f"{self.label}: {self.text_en or self.text_gu}"

    def text(self, lang):
        if lang == "en" and self.text_en:
            return self.text_en
        return self.text_gu


class Participant(models.Model):
    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=10, unique=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True)
    school_name = models.CharField(max_length=255)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.mobile})"


class Attempt(models.Model):
    PHASE_PRE = "pre"
    PHASE_POST = "post"
    PHASE_CHOICES = [(PHASE_PRE, "Pre-test"), (PHASE_POST, "Post-test")]

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = [(STATUS_IN_PROGRESS, "In progress"), (STATUS_SUBMITTED, "Submitted")]

    REASON_MANUAL = "manual"
    REASON_TIMEOUT = "timeout"
    REASON_ADMIN_CLOSE = "admin_close"
    REASON_CHOICES = [
        (REASON_MANUAL, "Manual"),
        (REASON_TIMEOUT, "Timeout"),
        (REASON_ADMIN_CLOSE, "Admin closed phase"),
    ]

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="attempts")
    phase = models.CharField(max_length=4, choices=PHASE_CHOICES)
    snapshot_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    snapshot_school_name = models.CharField(max_length=255, blank=True)
    snapshot_designation = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submit_reason = models.CharField(max_length=12, choices=REASON_CHOICES, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    had_pre_test = models.BooleanField(default=True, help_text="False if this is a post-test with no matching pre-test")

    class Meta:
        unique_together = [("quiz", "participant", "phase")]

    def __str__(self):
        return f"{self.participant} - {self.quiz} ({self.phase})"

    def is_expired(self):
        return bool(self.deadline) and timezone.now() > self.deadline

    def remaining_seconds(self):
        if not self.deadline:
            return None
        delta = (self.deadline - timezone.now()).total_seconds()
        return max(0, int(delta))

    def auto_submit(self, reason):
        if self.status == self.STATUS_SUBMITTED:
            return
        self.compute_score()
        self.status = self.STATUS_SUBMITTED
        self.submitted_at = timezone.now()
        self.submit_reason = reason
        self.save()

    def compute_score(self):
        answers = self.answers.select_related("option")
        correct = sum(1 for a in answers if a.is_correct)
        self.score = correct
        self.total = self.quiz.questions.count()


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    option = models.ForeignKey(Option, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)
    locked = models.BooleanField(default=False)

    class Meta:
        unique_together = [("attempt", "question")]

    def __str__(self):
        return f"{self.attempt} - Q{self.question.order}"
