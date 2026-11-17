import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Used to build the full, copyable public quiz link in the admin.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000" if DEBUG else "https://ceequiz.thecadlabs.com")

INSTALLED_APPS = [
    "jazzmin",  # must come before django.contrib.admin so its templates win
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "quiz",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "quiz.context_processors.language",
                "quiz.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "ceequiz"),
        "USER": os.environ.get("POSTGRES_USER", "ceequiz"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "ceequiz"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# The CEE logo (static/brand/cee-logo.png) isn't supplied yet — without this,
# WhiteNoise's manifest storage raises a hard 500 for any {% static %} tag
# pointing at a file that doesn't exist, instead of just leaving a broken
# image. Keep this off once the real logo file is committed.
WHITENOISE_MANIFEST_STRICT = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = "admin:index"

# Security
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]

# App settings
REMEMBER_HOURS = int(os.environ.get("REMEMBER_HOURS", "3"))
REMEMBER_COOKIE_NAME = "ceequiz_pid"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Admin theme (django-jazzmin). CAD Labs branding lives here instead of a
# hand-rolled admin/base_site.html override, since that's the supported way
# to customise Jazzmin's chrome — a raw template override fights its layout.
JAZZMIN_SETTINGS = {
    "site_title": "CEE Quiz Admin",
    "site_header": "CEE Quiz",
    "site_brand": "CAD Labs Technology",
    "site_logo": "brand/cadlabs-icon.png",
    "login_logo": "brand/cadlabs-icon.png",
    "site_logo_classes": "img-circle",
    "site_icon": "brand/cadlabs-icon.png",
    "welcome_sign": "CEE Quiz — sign in to manage pre/post tests",
    "copyright": "Made by CAD Labs Technology LLP",
    "search_model": ["quiz.Quiz", "quiz.Participant"],
    "show_ui_builder": False,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "quiz", "quiz.Quiz", "quiz.Question", "quiz.District", "quiz.School",
        "quiz.Participant", "quiz.Attempt", "quiz.Answer", "auth", "axes",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "quiz.Quiz": "fas fa-poll-h",
        "quiz.Question": "fas fa-question-circle",
        "quiz.Option": "fas fa-list-ul",
        "quiz.District": "fas fa-map-marker-alt",
        "quiz.School": "fas fa-school",
        "quiz.Participant": "fas fa-user-graduate",
        "quiz.Attempt": "fas fa-tasks",
        "quiz.Answer": "fas fa-check-square",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "custom_css": "css/admin-custom.css",
    "show_sidebar": True,
    "changeform_format": "horizontal_tabs",
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    # "flatly" (and most bootswatch themes) @import a Google Font over the
    # CDN on every admin page load — "default" is the same Bootstrap 5 +
    # AdminLTE look with no external font request.
    "theme": "default",
    "dark_mode_theme": None,
    "navbar": "navbar-dark",
    "navbar_fixed": True,
    "brand_colour": "navbar-success",
    "accent": "accent-success",
    "sidebar": "sidebar-dark-success",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "button_classes": {
        "primary": "btn-success",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
