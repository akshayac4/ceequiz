import json

from django.conf import settings
from django.core import signing
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ParticipantDetailsForm
from .models import Answer, Attempt, Option, Participant, Question, Quiz

COOKIE_SALT = "ceequiz.participant"


def _signer():
    return signing.TimestampSigner(salt=COOKIE_SALT)


def _get_participant_from_cookie(request):
    token = request.COOKIES.get(settings.REMEMBER_COOKIE_NAME)
    if not token:
        return None
    try:
        participant_id = _signer().unsign(token, max_age=settings.REMEMBER_HOURS * 3600)
    except signing.BadSignature:
        return None
    return Participant.objects.filter(pk=participant_id).first()


def _set_participant_cookie(response, participant):
    token = _signer().sign(str(participant.pk))
    response.set_cookie(
        settings.REMEMBER_COOKIE_NAME,
        token,
        max_age=settings.REMEMBER_HOURS * 3600,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def set_language(request, lang):
    if lang not in ("gu", "en"):
        lang = "gu"
    next_url = request.GET.get("next") or "/"
    response = redirect(next_url)
    response.set_cookie("ceequiz_lang", lang, max_age=365 * 24 * 3600)
    return response


def _current_attempt(quiz, participant, phase):
    return Attempt.objects.filter(quiz=quiz, participant=participant, phase=phase).first()


def _maybe_autosubmit(attempt):
    if attempt and attempt.status == Attempt.STATUS_IN_PROGRESS and attempt.is_expired():
        attempt.auto_submit(Attempt.REASON_TIMEOUT)
    return attempt


def quiz_entry(request, code):
    quiz = get_object_or_404(Quiz, code=code)

    if quiz.status == Quiz.STATUS_DRAFT:
        return render(request, "quiz/not_open.html", {"quiz": quiz, "show_cadlabs_badge": True})
    if quiz.status == Quiz.STATUS_CLOSED:
        return render(request, "quiz/closed.html", {"quiz": quiz, "show_cadlabs_badge": True})
    if quiz.status == Quiz.STATUS_PRE_CLOSED:
        return render(request, "quiz/waiting.html", {"quiz": quiz, "show_cadlabs_badge": True})

    phase = quiz.current_phase()
    participant = _get_participant_from_cookie(request)

    if not participant:
        form = ParticipantDetailsForm()
        return render(request, "quiz/details_form.html", {"quiz": quiz, "form": form})

    attempt = _maybe_autosubmit(_current_attempt(quiz, participant, phase))

    if attempt:
        if attempt.status == Attempt.STATUS_SUBMITTED:
            return render(request, "quiz/thankyou.html", {"quiz": quiz, "show_cadlabs_badge": True})
        return redirect("quiz:question", code=quiz.code, order=_first_unanswered_order(attempt))

    return render(request, "quiz/continuing.html", {"quiz": quiz, "participant": participant})


@require_POST
def start_attempt(request, code):
    quiz = get_object_or_404(Quiz, code=code)
    if quiz.status not in (Quiz.STATUS_PRE_OPEN, Quiz.STATUS_POST_OPEN):
        return redirect("quiz:entry", code=quiz.code)

    phase = quiz.current_phase()
    participant = _get_participant_from_cookie(request)
    response = None

    if participant is None:
        form = ParticipantDetailsForm(request.POST)
        if not form.is_valid():
            return render(request, "quiz/details_form.html", {"quiz": quiz, "form": form})
        data = form.cleaned_data
        participant, _created = Participant.objects.get_or_create(
            mobile=data["mobile"],
            defaults={
                "name": data["name"],
                "district": data["district"],
                "school_name": data["school_name"],
                "designation": data["designation"],
            },
        )
        participant.name = data["name"]
        participant.district = data["district"]
        participant.school_name = data["school_name"]
        participant.designation = data["designation"]
        participant.save()

    attempt, created = Attempt.objects.get_or_create(
        quiz=quiz,
        participant=participant,
        phase=phase,
        defaults={
            "snapshot_district": participant.district,
            "snapshot_school_name": participant.school_name,
            "snapshot_designation": participant.designation,
            "started_at": timezone.now(),
            "deadline": timezone.now() + timezone.timedelta(minutes=quiz.duration_minutes) if quiz.duration_minutes else None,
        },
    )
    if created and phase == Attempt.PHASE_POST:
        attempt.had_pre_test = Attempt.objects.filter(
            quiz=quiz, participant=participant, phase=Attempt.PHASE_PRE, status=Attempt.STATUS_SUBMITTED
        ).exists()
        attempt.save(update_fields=["had_pre_test"])

    target = redirect("quiz:question", code=quiz.code, order=_first_unanswered_order(attempt))
    _set_participant_cookie(target, participant)
    return target


def not_you(request, code):
    response = redirect("quiz:entry", code=code)
    response.delete_cookie(settings.REMEMBER_COOKIE_NAME)
    return response


def _first_unanswered_order(attempt):
    answered_orders = set(attempt.answers.values_list("question__order", flat=True))
    for q in attempt.quiz.questions.all():
        if q.order not in answered_orders:
            return q.order
    return attempt.quiz.questions.count() or 1


def question_view(request, code, order):
    quiz = get_object_or_404(Quiz, code=code)
    phase = quiz.current_phase()
    if phase is None:
        return redirect("quiz:entry", code=quiz.code)

    participant = _get_participant_from_cookie(request)
    if not participant:
        return redirect("quiz:entry", code=quiz.code)

    attempt = _maybe_autosubmit(_current_attempt(quiz, participant, phase))
    if not attempt:
        return redirect("quiz:entry", code=quiz.code)
    if attempt.status == Attempt.STATUS_SUBMITTED:
        return render(request, "quiz/thankyou.html", {"quiz": quiz, "show_cadlabs_badge": True})

    question = get_object_or_404(Question, quiz=quiz, order=order)
    total = quiz.questions.count()
    existing_answer = attempt.answers.filter(question=question).select_related("option").first()

    options = list(question.options.all())
    reveal = None
    if phase == Attempt.PHASE_POST and existing_answer and existing_answer.locked:
        reveal = {
            "selected_label": existing_answer.option.label if existing_answer.option else None,
            "correct_label": next((o.label for o in options if o.is_correct), None),
            "is_correct": existing_answer.is_correct,
        }

    context = {
        "quiz": quiz,
        "phase": phase,
        "question": question,
        "options": options,
        "order": order,
        "total": total,
        "selected_label": existing_answer.option.label if existing_answer and existing_answer.option else None,
        "reveal": reveal,
        "remaining_seconds": attempt.remaining_seconds(),
        "has_prev": order > 1,
        "has_next": order < total,
        "is_last": order >= total,
    }
    return render(request, "quiz/question.html", context)


@require_POST
def save_answer(request, code, order):
    quiz = get_object_or_404(Quiz, code=code)
    phase = quiz.current_phase()
    participant = _get_participant_from_cookie(request)
    if not participant or phase is None:
        return HttpResponseBadRequest("no active session")

    attempt = _maybe_autosubmit(_current_attempt(quiz, participant, phase))
    if not attempt or attempt.status == Attempt.STATUS_SUBMITTED:
        return JsonResponse({"error": "attempt_closed"}, status=409)
    if attempt.is_expired():
        return JsonResponse({"error": "expired"}, status=409)

    question = get_object_or_404(Question, quiz=quiz, order=order)
    label = request.POST.get("option")
    option = Option.objects.filter(question=question, label=label).first() if label else None

    answer, _created = Answer.objects.get_or_create(attempt=attempt, question=question)

    if phase == Attempt.PHASE_POST and answer.locked:
        return JsonResponse({"error": "locked"}, status=403)

    answer.option = option
    answer.is_correct = bool(option and option.is_correct)
    if phase == Attempt.PHASE_POST:
        answer.locked = True
    answer.save()

    payload = {"ok": True}
    if phase == Attempt.PHASE_POST:
        correct_option = question.options.filter(is_correct=True).first()
        payload.update(
            {
                "is_correct": answer.is_correct,
                "correct_label": correct_option.label if correct_option else None,
                "selected_label": option.label if option else None,
            }
        )
    return JsonResponse(payload)


@require_POST
def submit_attempt(request, code):
    quiz = get_object_or_404(Quiz, code=code)
    phase = quiz.current_phase()
    participant = _get_participant_from_cookie(request)
    if not participant or phase is None:
        return redirect("quiz:entry", code=quiz.code)

    attempt = _current_attempt(quiz, participant, phase)
    if attempt and attempt.status == Attempt.STATUS_IN_PROGRESS:
        attempt.auto_submit(Attempt.REASON_MANUAL)
    return render(request, "quiz/thankyou.html", {"quiz": quiz, "show_cadlabs_badge": True})


def quiz_status(request, code):
    quiz = get_object_or_404(Quiz, code=code)
    return JsonResponse({"status": quiz.status})
