def language(request):
    lang = request.COOKIES.get("ceequiz_lang", "gu")
    if lang not in ("gu", "en"):
        lang = "gu"
    return {"LANG": lang}
