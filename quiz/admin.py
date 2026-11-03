import io

import openpyxl
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Answer, Attempt, District, Option, Participant, Question, Quiz, School, generate_quiz_code

admin.site.site_header = "CEE Quiz — Admin"
admin.site.site_title = "CEE Quiz Admin"
admin.site.index_title = "Administration"

UPLOAD_COLUMNS = [
    "order", "question_gu", "question_en",
    "A_gu", "A_en", "B_gu", "B_en",
    "C_gu", "C_en", "D_gu", "D_en",
    "correct",
]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_gu", "active"]
    list_editable = ["active"]
    search_fields = ["name_en", "name_gu"]


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["name", "district", "udise_code"]
    list_filter = ["district"]
    search_fields = ["name", "udise_code"]


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4
    max_num = 4
    fields = ["label", "text_gu", "text_en", "is_correct"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["quiz", "order", "text_en", "has_correct_option"]
    list_filter = ["quiz"]
    inlines = [OptionInline]
    ordering = ["quiz", "order"]

    def has_correct_option(self, obj):
        return obj.options.filter(is_correct=True).exists()
    has_correct_option.boolean = True


class QuestionReadonlyInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["order", "text_en", "edit_link"]
    readonly_fields = ["order", "text_en", "edit_link"]
    can_delete = False
    show_change_link = False

    def edit_link(self, obj):
        if obj.pk:
            url = reverse("admin:quiz_question_change", args=[obj.pk])
            return format_html('<a href="{}">Edit options</a>', url)
        return ""
    edit_link.short_description = "Options"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title_en", "district", "code", "status", "audience", "duration_minutes", "created_at", "quiz_link"]
    list_filter = ["status", "audience", "district"]
    readonly_fields = ["code", "status_actions", "quiz_link", "monitor_box", "bulk_upload_box", "duplicate_box"]
    inlines = [QuestionReadonlyInline]
    actions = ["duplicate_quiz"]
    fields = [
        "title_gu", "title_en", "code", "event_name", "district", "audience",
        "duration_minutes", "phase_closes_at",
        "instructions_gu", "instructions_en",
        "status_actions", "quiz_link", "monitor_box", "bulk_upload_box", "duplicate_box",
    ]

    def bulk_upload_box(self, obj):
        if not obj.pk:
            return "Save the quiz first."
        template_url = reverse("admin:quiz_quiz_question_template")
        upload_url = reverse("admin:quiz_quiz_upload_questions", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Download Excel template</a> '
            '<a class="button" href="{}">Upload questions</a>',
            template_url, upload_url,
        )
    bulk_upload_box.short_description = "Bulk question upload"

    def duplicate_box(self, obj):
        if not obj.pk:
            return "Save the quiz first."
        url = reverse("admin:quiz_quiz_duplicate", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Duplicate this quiz</a> '
            '<span style="color:#666">Copies all questions and options as a new draft — '
            'pick a different district (and title) on the copy, no retyping needed.</span>',
            url,
        )
    duplicate_box.short_description = "Reuse for another district"

    def quiz_link(self, obj):
        if not obj.pk:
            return "-"
        from django.conf import settings
        url = f"{settings.SITE_URL.rstrip('/')}/q/{obj.code}/"
        return format_html(
            '<input type="text" readonly value="{0}" id="quiz-public-link" '
            'style="width:360px;padding:6px;font-family:monospace;" '
            'onclick="this.select()">'
            '<button type="button" class="button" style="margin-left:8px" '
            'onclick="navigator.clipboard.writeText(\'{0}\');'
            'this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'Copy link\',1500);">'
            'Copy link</button>',
            url,
        )
    quiz_link.short_description = "Public link (same link for pre and post test)"

    def status_actions(self, obj):
        if not obj.pk:
            return "Save the quiz first."
        buttons = []
        if obj.can_open_pre():
            buttons.append(("open_pre", "Open pre-test"))
        if obj.can_close_pre():
            buttons.append(("close_pre", "Close pre-test"))
        if obj.can_open_post():
            buttons.append(("open_post", "Open post-test"))
        if obj.can_close():
            buttons.append(("close", "Close quiz"))
        if obj.questions_missing_correct_option():
            warn = '<p style="color:#B3261E">Every question needs a correct option ticked before opening.</p>'
        else:
            warn = ""
        html = f'<p><strong>Current status:</strong> {obj.get_status_display()}</p>' + warn
        for action, label in buttons:
            url = reverse("admin:quiz_quiz_transition", args=[obj.pk, action])
            html += (
                f'<a class="button" style="margin-right:8px" '
                f'href="{url}">{label}</a>'
            )
        return format_html(html)
    status_actions.short_description = "Lifecycle"

    def monitor_box(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:quiz_quiz_monitor", args=[obj.pk])
        return format_html(
            '<div id="live-monitor" data-url="{}"><em>Loading live monitor…</em></div>'
            '<script>'
            'function refreshMonitor(){{'
            'fetch("{}").then(r=>r.json()).then(d=>{{'
            'document.getElementById("live-monitor").innerHTML='
            '"Joined: "+d.joined+" &middot; In progress: "+d.in_progress+" &middot; Submitted: "+d.submitted;'
            '}});}}'
            'refreshMonitor();setInterval(refreshMonitor,10000);'
            '</script>',
            url, url,
        )
    monitor_box.short_description = "Live monitor (current phase)"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:pk>/transition/<str:action>/", self.admin_site.admin_view(self.transition_view), name="quiz_quiz_transition"),
            path("<int:pk>/monitor.json", self.admin_site.admin_view(self.monitor_view), name="quiz_quiz_monitor"),
            path("<int:pk>/upload-questions/", self.admin_site.admin_view(self.upload_questions_view), name="quiz_quiz_upload_questions"),
            path("question-template.xlsx", self.admin_site.admin_view(self.template_view), name="quiz_quiz_question_template"),
            path("<int:pk>/duplicate/", self.admin_site.admin_view(self.duplicate_view), name="quiz_quiz_duplicate"),
        ]
        return custom + urls

    def duplicate_view(self, request, pk):
        quiz = self.get_object(request, pk)
        if quiz is None:
            messages.error(request, "Quiz not found.")
            return redirect("admin:quiz_quiz_changelist")
        new_quiz = self._duplicate(quiz)
        messages.success(request, f"Duplicated as a new draft. Pick the district and tweak the title below.")
        return redirect("admin:quiz_quiz_change", new_quiz.pk)

    def transition_view(self, request, pk, action):
        quiz = self.get_object(request, pk)
        if quiz is None:
            messages.error(request, "Quiz not found.")
            return redirect("admin:quiz_quiz_changelist")

        if action == "open_pre" and quiz.can_open_pre():
            quiz.status = Quiz.STATUS_PRE_OPEN
        elif action == "close_pre" and quiz.can_close_pre():
            quiz.status = Quiz.STATUS_PRE_CLOSED
            for attempt in quiz.attempts.filter(phase=Attempt.PHASE_PRE, status=Attempt.STATUS_IN_PROGRESS):
                attempt.auto_submit(Attempt.REASON_ADMIN_CLOSE)
        elif action == "open_post" and quiz.can_open_post():
            quiz.status = Quiz.STATUS_POST_OPEN
        elif action == "close" and quiz.can_close():
            quiz.status = Quiz.STATUS_CLOSED
            for attempt in quiz.attempts.filter(phase=Attempt.PHASE_POST, status=Attempt.STATUS_IN_PROGRESS):
                attempt.auto_submit(Attempt.REASON_ADMIN_CLOSE)
        else:
            messages.error(request, "That transition isn't valid right now.")
            return redirect("admin:quiz_quiz_change", pk)

        quiz.save()
        messages.success(request, f"Quiz status changed to {quiz.get_status_display()}.")
        return redirect("admin:quiz_quiz_change", pk)

    def monitor_view(self, request, pk):
        quiz = self.get_object(request, pk)
        phase = quiz.current_phase() if quiz else None
        if not quiz or not phase:
            return HttpResponse('{"joined": 0, "in_progress": 0, "submitted": 0}', content_type="application/json")
        qs = quiz.attempts.filter(phase=phase)
        data = {
            "joined": qs.count(),
            "in_progress": qs.filter(status=Attempt.STATUS_IN_PROGRESS).count(),
            "submitted": qs.filter(status=Attempt.STATUS_SUBMITTED).count(),
        }
        import json
        return HttpResponse(json.dumps(data), content_type="application/json")

    def template_view(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Questions"
        ws.append(UPLOAD_COLUMNS)
        ws.append([
            1, "ગુજરાતી પ્રશ્ન?", "Sample question?",
            "વિકલ્પ A", "Option A", "વિકલ્પ B", "Option B",
            "વિકલ્પ C", "Option C", "વિકલ્પ D", "Option D",
            "A",
        ])
        buf = io.BytesIO()
        wb.save(buf)
        response = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="ceequiz_question_template.xlsx"'
        return response

    def upload_questions_view(self, request, pk):
        quiz = self.get_object(request, pk)
        if quiz is None:
            messages.error(request, "Quiz not found.")
            return redirect("admin:quiz_quiz_changelist")

        if request.method == "POST" and request.FILES.get("file"):
            errors = []
            rows = []
            wb = openpyxl.load_workbook(request.FILES["file"], data_only=True)
            ws = wb.active
            header = [str(c.value).strip() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
            if header != UPLOAD_COLUMNS:
                errors.append(f"Header row must be exactly: {', '.join(UPLOAD_COLUMNS)}")
            else:
                for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    values = [c.value for c in row]
                    if all(v in (None, "") for v in values):
                        continue
                    record = dict(zip(UPLOAD_COLUMNS, values))
                    row_errors = []
                    try:
                        record["order"] = int(record["order"])
                    except (TypeError, ValueError):
                        row_errors.append("order must be a number")
                    if not record.get("question_gu"):
                        row_errors.append("question_gu is required")
                    for label in ["A", "B", "C", "D"]:
                        if not record.get(f"{label}_gu"):
                            row_errors.append(f"{label}_gu is required")
                    correct = str(record.get("correct") or "").strip().upper()
                    if correct not in ["A", "B", "C", "D"]:
                        row_errors.append("correct must be one of A/B/C/D")
                    record["correct"] = correct
                    if row_errors:
                        errors.append(f"Row {i}: " + "; ".join(row_errors))
                    else:
                        rows.append(record)

            if errors:
                for e in errors:
                    messages.error(request, e)
                return render(request, "admin/quiz/upload_questions.html", {"quiz": quiz})

            for record in rows:
                question, _ = Question.objects.update_or_create(
                    quiz=quiz, order=record["order"],
                    defaults={"text_gu": record["question_gu"], "text_en": record.get("question_en") or ""},
                )
                for label in ["A", "B", "C", "D"]:
                    Option.objects.update_or_create(
                        question=question, label=label,
                        defaults={
                            "text_gu": record[f"{label}_gu"],
                            "text_en": record.get(f"{label}_en") or "",
                            "is_correct": label == record["correct"],
                        },
                    )
            messages.success(request, f"Imported {len(rows)} question(s).")
            return redirect("admin:quiz_quiz_change", pk)

        return render(request, "admin/quiz/upload_questions.html", {"quiz": quiz})

    def _duplicate(self, quiz):
        questions = list(quiz.questions.prefetch_related("options"))
        quiz.pk = None
        quiz.code = generate_quiz_code()
        quiz.status = Quiz.STATUS_DRAFT
        quiz.title_en = f"{quiz.title_en} (copy)"
        quiz.title_gu = f"{quiz.title_gu} (copy)"
        quiz.save()
        for q in questions:
            options = list(q.options.all())
            q.pk = None
            q.quiz = quiz
            q.save()
            for opt in options:
                opt.pk = None
                opt.question = q
                opt.save()
        return quiz

    def duplicate_quiz(self, request, queryset):
        for quiz in queryset:
            self._duplicate(quiz)
        messages.success(request, "Quiz duplicated as a new draft.")
    duplicate_quiz.short_description = "Duplicate selected quiz"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ["name", "mobile", "district", "school_name", "designation", "created_at"]
    search_fields = ["name", "mobile", "school_name"]
    list_filter = ["district"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["participant", "quiz", "phase", "status", "score", "total", "submitted_at"]
    list_filter = ["quiz", "phase", "status"]
    search_fields = ["participant__name", "participant__mobile"]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["attempt", "question", "option", "is_correct", "locked"]
    list_filter = ["is_correct", "locked"]
