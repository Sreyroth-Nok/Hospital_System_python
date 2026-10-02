"""
validator.py - Every value typed by a user passes through here.
Owner: Person 2
"""

from datetime import datetime

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class ValidationError(Exception):
    """Raised when a value cannot be accepted."""


def input_text(prompt, allow_empty=False, max_len=100):
    while True:
        value = input(prompt).strip()
        if not value and allow_empty:
            return ""
        if not value:
            print("  ! This field cannot be empty.")
        elif len(value) > max_len:
            print(f"  ! Please keep it under {max_len} characters.")
        else:
            return value


def input_int(prompt, minimum=None, maximum=None, allow_empty=False):
    while True:
        raw = input(prompt).strip()
        if not raw and allow_empty:
            return None
        try:
            value = int(raw)
        except ValueError:
            print("  ! Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"  ! Must be at least {minimum}.")
        elif maximum is not None and value > maximum:
            print(f"  ! Must be at most {maximum}.")
        else:
            return value


def input_float(prompt, minimum=0.0, allow_empty=False):
    while True:
        raw = input(prompt).strip()
        if not raw and allow_empty:
            return None
        try:
            value = float(raw)
        except ValueError:
            print("  ! Please enter a number, for example 25 or 25.50.")
            continue
        if value < minimum:
            print(f"  ! Must be at least {minimum}.")
        else:
            return round(value, 2)


def input_phone(prompt, allow_empty=False):
    while True:
        value = input(prompt).strip()
        if not value and allow_empty:
            return ""
        if value.isdigit() and 8 <= len(value) <= 15:
            return value
        print("  ! Phone must be 8 to 15 digits, numbers only.")


def input_gender(prompt="Gender (M/F)      : "):
    while True:
        value = input(prompt).strip().upper()
        if value in ("M", "F"):
            return value
        print("  ! Please type M or F.")


def input_date(prompt, no_past=False, allow_empty=False):
    """Read a date as YYYY-MM-DD."""
    while True:
        value = input(prompt).strip()
        if not value and allow_empty:
            return ""
        try:
            parsed = datetime.strptime(value, DATE_FMT).date()
        except ValueError:
            print("  ! Wrong format. Use YYYY-MM-DD, for example 2026-10-21.")
            continue
        if no_past and parsed < datetime.now().date():
            print("  ! That date has already passed.")
            continue
        return value


def input_time(prompt):
    """Read a time as HH:MM."""
    while True:
        value = input(prompt).strip()
        try:
            datetime.strptime(value, TIME_FMT)
            return value
        except ValueError:
            print("  ! Wrong format. Use HH:MM, for example 14:30.")


def input_day(prompt="Day (Mon..Sun)    : "):
    while True:
        value = input(prompt).strip().title()[:3]
        if value in DAYS:
            return value
        print(f"  ! Use one of: {', '.join(DAYS)}")


def input_choice(prompt, choices):
    """Read one value from a fixed list, case-insensitive."""
    lowered = {c.lower(): c for c in choices}
    while True:
        value = input(prompt).strip().lower()
        if value in lowered:
            return lowered[value]
        print(f"  ! Choose one of: {', '.join(choices)}")


def confirm(prompt="Are you sure? (y/n): "):
    return input(prompt).strip().lower() in ("y", "yes")


def weekday_of(date_str):
    """Mon, Tue ... for a YYYY-MM-DD string."""
    return datetime.strptime(date_str, DATE_FMT).strftime("%a")


def is_past(date_str, time_str=None):
    """True when the date, or the date and time, are already gone."""
    when = datetime.strptime(date_str, DATE_FMT)
    if time_str:
        when = datetime.strptime(f"{date_str} {time_str}", f"{DATE_FMT} {TIME_FMT}")
        return when < datetime.now()
    return when.date() < datetime.now().date()


def today():
    return datetime.now().strftime(DATE_FMT)


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Parsers used by the GUI. The rules are the same as the input_* helpers
# above, but these take a value instead of asking at the terminal, so one
# set of rules serves both interfaces.
# ---------------------------------------------------------------------------

def parse_text(value, label="This field", allow_empty=False, max_len=120):
    value = (value or "").strip()
    if not value and not allow_empty:
        raise ValidationError(f"{label} cannot be empty.")
    if len(value) > max_len:
        raise ValidationError(f"{label} must be under {max_len} characters.")
    return value


def parse_int(value, label="Value", minimum=None, maximum=None, allow_empty=False):
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return None
        raise ValidationError(f"{label} cannot be empty.")
    try:
        number = int(raw)
    except ValueError:
        raise ValidationError(f"{label} must be a whole number.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{label} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{label} must be at most {maximum}.")
    return number


def parse_float(value, label="Value", minimum=0.0, allow_empty=False):
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return None
        raise ValidationError(f"{label} cannot be empty.")
    try:
        number = float(raw)
    except ValueError:
        raise ValidationError(f"{label} must be a number, for example 25.50.")
    if number < minimum:
        raise ValidationError(f"{label} must be at least {minimum}.")
    return round(number, 2)


def parse_phone(value, label="Phone", allow_empty=False):
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return ""
        raise ValidationError(f"{label} cannot be empty.")
    if not raw.isdigit() or not 8 <= len(raw) <= 15:
        raise ValidationError(f"{label} must be 8 to 15 digits, numbers only.")
    return raw


def parse_gender(value, label="Gender"):
    raw = str(value or "").strip().upper()[:1]
    if raw not in ("M", "F"):
        raise ValidationError(f"{label} must be M or F.")
    return raw


def parse_date(value, label="Date", no_past=False, allow_empty=False):
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return ""
        raise ValidationError(f"{label} cannot be empty.")
    try:
        parsed = datetime.strptime(raw, DATE_FMT).date()
    except ValueError:
        raise ValidationError(f"{label} must look like 2026-10-21.")
    if no_past and parsed < datetime.now().date():
        raise ValidationError(f"{label} has already passed.")
    return raw


def parse_time(value, label="Time", allow_empty=False):
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return ""
        raise ValidationError(f"{label} cannot be empty.")
    try:
        datetime.strptime(raw, TIME_FMT)
    except ValueError:
        raise ValidationError(f"{label} must look like 14:30.")
    return raw


def parse_day(value, label="Day"):
    raw = str(value or "").strip().title()[:3]
    if raw not in DAYS:
        raise ValidationError(f"{label} must be one of: {', '.join(DAYS)}")
    return raw
