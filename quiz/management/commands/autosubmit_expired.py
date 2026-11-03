from django.core.management.base import BaseCommand
from django.utils import timezone

from quiz.models import Attempt, Quiz


class Command(BaseCommand):
    help = "Auto-submit attempts whose deadline has passed, and auto-close phases past phase_closes_at. Run every minute via cron."

    def handle(self, *args, **options):
        now = timezone.now()

        expired_attempts = Attempt.objects.filter(status=Attempt.STATUS_IN_PROGRESS, deadline__lt=now)
        count = 0
        for attempt in expired_attempts:
            attempt.auto_submit(Attempt.REASON_TIMEOUT)
            count += 1
        if count:
            self.stdout.write(f"Auto-submitted {count} expired attempt(s).")

        due_quizzes = Quiz.objects.filter(phase_closes_at__lt=now).exclude(status__in=[Quiz.STATUS_DRAFT, Quiz.STATUS_CLOSED])
        for quiz in due_quizzes:
            if quiz.status == Quiz.STATUS_PRE_OPEN:
                quiz.status = Quiz.STATUS_PRE_CLOSED
                for attempt in quiz.attempts.filter(phase=Attempt.PHASE_PRE, status=Attempt.STATUS_IN_PROGRESS):
                    attempt.auto_submit(Attempt.REASON_ADMIN_CLOSE)
            elif quiz.status == Quiz.STATUS_POST_OPEN:
                quiz.status = Quiz.STATUS_CLOSED
                for attempt in quiz.attempts.filter(phase=Attempt.PHASE_POST, status=Attempt.STATUS_IN_PROGRESS):
                    attempt.auto_submit(Attempt.REASON_ADMIN_CLOSE)
            else:
                continue
            quiz.phase_closes_at = None
            quiz.save()
            self.stdout.write(f"Auto-closed phase for quiz '{quiz}', now {quiz.get_status_display()}.")
