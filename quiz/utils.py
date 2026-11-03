import re


def normalize_mobile(raw):
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits[-10:] if len(digits) >= 10 else digits


MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def is_valid_mobile(mobile):
    return bool(MOBILE_RE.match(mobile))
