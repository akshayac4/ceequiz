from django.conf import settings


def language(request):
    lang = request.COOKIES.get("ceequiz_lang", "gu")
    if lang not in ("gu", "en"):
        lang = "gu"
    return {"LANG": lang}


def branding(request):
    # The CEE logo file hasn't been supplied yet. WhiteNoise's manifest
    # storage raises a hard error for a {% static %} tag pointing at a file
    # that doesn't exist on disk, so gate the <img> on it actually being
    # there rather than relying on a client-side onerror handler.
    return {"cee_logo_exists": (settings.STATIC_ROOT / "brand" / "cee-logo.png").exists()}
