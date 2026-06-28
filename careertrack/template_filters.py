from datetime import datetime


def display_date(value):
    if not value:
        return "Not set"
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%b %d, %Y")


def display_datetime(value):
    if not value:
        return "Not set"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%b %d, %Y at %I:%M %p")


def date_input(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")
