from datetime import datetime

from django.utils import timezone

from quiz.models import Attempt


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def filtered_attempts(get, include_phase=True):
    """Submitted attempts matching the dashboard filters.

    include_phase=False omits the phase filter, useful for pairing pre/post
    per participant regardless of which phase the page is currently showing.
    """
    qs = Attempt.objects.filter(status=Attempt.STATUS_SUBMITTED).select_related(
        "participant", "quiz", "snapshot_district"
    )

    quiz_id = get.get("quiz")
    if quiz_id:
        qs = qs.filter(quiz_id=quiz_id)

    if include_phase:
        phase = get.get("phase")
        if phase in (Attempt.PHASE_PRE, Attempt.PHASE_POST):
            qs = qs.filter(phase=phase)

    district_id = get.get("district")
    if district_id:
        qs = qs.filter(snapshot_district_id=district_id)

    school = get.get("school")
    if school:
        qs = qs.filter(snapshot_school_name__icontains=school)

    designation = get.get("designation")
    if designation:
        qs = qs.filter(snapshot_designation__icontains=designation)

    date_from = parse_date(get.get("date_from"))
    date_to = parse_date(get.get("date_to"))
    if date_from:
        qs = qs.filter(submitted_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(submitted_at__date__lte=date_to)

    return qs


def pct(attempt):
    if not attempt.total:
        return 0.0
    return round(attempt.score * 100.0 / attempt.total, 1)
