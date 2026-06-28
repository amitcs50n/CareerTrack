from datetime import datetime


def clean_text(value):
    value = (value or "").strip()
    return value or None


def parse_datetime_local(value):
    value = clean_text(value)
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


def is_safe_next_url(next_url):
    return bool(next_url) and next_url.startswith("/") and not next_url.startswith("//")
