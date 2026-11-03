from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("lang/<str:lang>/", views.set_language, name="set_language"),
    path("q/<str:code>/", views.quiz_entry, name="entry"),
    path("q/<str:code>/start/", views.start_attempt, name="start_attempt"),
    path("q/<str:code>/not-you/", views.not_you, name="not_you"),
    path("q/<str:code>/status/", views.quiz_status, name="status"),
    path("q/<str:code>/progress/", views.attempt_progress, name="progress"),
    path("q/<str:code>/submit/", views.submit_attempt, name="submit_attempt"),
    path("q/<str:code>/question/<int:order>/", views.question_view, name="question"),
    path("q/<str:code>/answer/<int:order>/", views.save_answer, name="save_answer"),
]
