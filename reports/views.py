import io
from collections import defaultdict

import openpyxl
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from quiz.models import Answer, Attempt, District, Question, Quiz

from .filters import filtered_attempts, pct


def _build_rows(get):
    base_qs = filtered_attempts(get, include_phase=False)
    phase = get.get("phase") if get.get("phase") in (Attempt.PHASE_PRE, Attempt.PHASE_POST) else None

    grouped = defaultdict(dict)
    for attempt in base_qs:
        grouped[(attempt.participant_id, attempt.quiz_id)][attempt.phase] = attempt

    rows = []
    for (_pid, _qid), phases in grouped.items():
        pre = phases.get(Attempt.PHASE_PRE)
        post = phases.get(Attempt.PHASE_POST)
        if phase == Attempt.PHASE_PRE and not pre:
            continue
        if phase == Attempt.PHASE_POST and not post:
            continue
        anchor = pre or post
        pre_pct = pct(pre) if pre else None
        post_pct = pct(post) if post else None
        gain = round(post_pct - pre_pct, 1) if pre_pct is not None and post_pct is not None else None
        rows.append({
            "participant": anchor.participant,
            "quiz": anchor.quiz,
            "district": (anchor.snapshot_district.name_en if anchor.snapshot_district else ""),
            "school": anchor.snapshot_school_name,
            "designation": anchor.snapshot_designation,
            "pre_score": pre.score if pre else None,
            "post_score": post.score if post else None,
            "pre_pct": pre_pct,
            "post_pct": post_pct,
            "gain": gain,
            "no_pre_test": post is not None and pre is None,
        })

    search = get.get("q", "").strip().lower()
    if search:
        rows = [
            r for r in rows
            if search in r["participant"].name.lower()
            or search in r["participant"].mobile
            or search in r["school"].lower()
        ]

    sort = get.get("sort", "-pre_pct")
    reverse = sort.startswith("-")
    key = sort.lstrip("-")
    if key in {"pre_pct", "post_pct", "gain", "pre_score", "post_score"}:
        rows.sort(key=lambda r: (r[key] is None, r[key] or 0), reverse=reverse)
    elif key == "name":
        rows.sort(key=lambda r: r["participant"].name.lower(), reverse=reverse)
    elif key == "school":
        rows.sort(key=lambda r: r["school"].lower(), reverse=reverse)

    return rows, base_qs, phase


def _summary(rows):
    pre_vals = [r["pre_pct"] for r in rows if r["pre_pct"] is not None]
    post_vals = [r["post_pct"] for r in rows if r["post_pct"] is not None]
    gain_vals = [r["gain"] for r in rows if r["gain"] is not None]
    return {
        "participants": len(rows),
        "pre_takers": len(pre_vals),
        "post_takers": len(post_vals),
        "took_both": len(gain_vals),
        "avg_pre": round(sum(pre_vals) / len(pre_vals), 1) if pre_vals else None,
        "avg_post": round(sum(post_vals) / len(post_vals), 1) if post_vals else None,
        "avg_gain": round(sum(gain_vals) / len(gain_vals), 1) if gain_vals else None,
    }


def _chart_data(rows, base_qs):
    by_district = defaultdict(lambda: {"pre": [], "post": []})
    by_school = defaultdict(lambda: {"pre": [], "post": []})
    for r in rows:
        d = r["district"] or "—"
        if r["pre_pct"] is not None:
            by_district[d]["pre"].append(r["pre_pct"])
            by_school[r["school"]]["pre"].append(r["pre_pct"])
        if r["post_pct"] is not None:
            by_district[d]["post"].append(r["post_pct"])
            by_school[r["school"]]["post"].append(r["post_pct"])

    def avg(vals):
        return round(sum(vals) / len(vals), 1) if vals else 0

    district_labels = sorted(by_district.keys())
    district_pre = [avg(by_district[d]["pre"]) for d in district_labels]
    district_post = [avg(by_district[d]["post"]) for d in district_labels]

    school_avgs = [(s, avg(v["pre"]), avg(v["post"])) for s, v in by_school.items()]
    school_avgs.sort(key=lambda t: t[2])
    bottom_n = school_avgs[:5]
    top_n = school_avgs[-5:]
    combined = bottom_n + [t for t in top_n if t not in bottom_n]
    school_labels = [t[0] for t in combined]
    school_pre = [t[1] for t in combined]
    school_post = [t[2] for t in combined]

    bins = [0, 0, 0, 0, 0]
    for a in base_qs:
        p = pct(a)
        idx = min(int(p // 20), 4)
        bins[idx] += 1

    return {
        "district_labels": district_labels,
        "district_pre": district_pre,
        "district_post": district_post,
        "school_labels": school_labels,
        "school_pre": school_pre,
        "school_post": school_post,
        "distribution_bins": bins,
    }


def _question_accuracy(get, quiz):
    if not quiz:
        return []
    base_qs = filtered_attempts(get, include_phase=False).filter(quiz=quiz)
    attempt_ids_pre = [a.id for a in base_qs if a.phase == Attempt.PHASE_PRE]
    attempt_ids_post = [a.id for a in base_qs if a.phase == Attempt.PHASE_POST]

    answers = Answer.objects.filter(attempt_id__in=attempt_ids_pre + attempt_ids_post).select_related("question")
    pre_stats = defaultdict(lambda: [0, 0])
    post_stats = defaultdict(lambda: [0, 0])
    pre_set = set(attempt_ids_pre)
    for ans in answers:
        bucket = pre_stats if ans.attempt_id in pre_set else post_stats
        bucket[ans.question_id][1] += 1
        if ans.is_correct:
            bucket[ans.question_id][0] += 1

    rows = []
    for q in quiz.questions.all():
        pre_correct, pre_total = pre_stats.get(q.id, [0, 0])
        post_correct, post_total = post_stats.get(q.id, [0, 0])
        rows.append({
            "question": q,
            "pre_pct": round(pre_correct * 100 / pre_total, 1) if pre_total else None,
            "post_pct": round(post_correct * 100 / post_total, 1) if post_total else None,
        })
    return rows


@staff_member_required
def dashboard(request):
    get = request.GET
    rows, base_qs, _phase = _build_rows(get)
    summary = _summary(rows)
    charts = _chart_data(rows, base_qs)

    quiz_id = get.get("quiz")
    quiz = Quiz.objects.filter(pk=quiz_id).first() if quiz_id else None
    question_rows = _question_accuracy(get, quiz)

    context = {
        "rows": rows,
        "summary": summary,
        "charts": charts,
        "question_rows": question_rows,
        "quiz": quiz,
        "quizzes": Quiz.objects.all(),
        "districts": District.objects.all(),
        "get": get,
    }
    return render(request, "reports/dashboard.html", context)


@staff_member_required
def export_excel(request):
    get = request.GET
    rows, _base_qs, _phase = _build_rows(get)
    quiz_id = get.get("quiz")
    quiz = Quiz.objects.filter(pk=quiz_id).first() if quiz_id else None
    question_rows = _question_accuracy(get, quiz)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Participants"
    ws.append(["Name", "Mobile", "District", "School", "Designation", "Pre score %", "Post score %", "Gain", "No pre-test"])
    for r in rows:
        ws.append([
            r["participant"].name, r["participant"].mobile, r["district"], r["school"], r["designation"],
            r["pre_pct"] if r["pre_pct"] is not None else "",
            r["post_pct"] if r["post_pct"] is not None else "",
            r["gain"] if r["gain"] is not None else "",
            "Yes" if r["no_pre_test"] else "",
        ])

    ws2 = wb.create_sheet("Question-wise accuracy")
    ws2.append(["Order", "Question (English)", "Question (Gujarati)", "Pre accuracy %", "Post accuracy %"])
    for qr in question_rows:
        ws2.append([
            qr["question"].order, qr["question"].text_en, qr["question"].text_gu,
            qr["pre_pct"] if qr["pre_pct"] is not None else "",
            qr["post_pct"] if qr["post_pct"] is not None else "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="ceequiz_report.xlsx"'
    return response
