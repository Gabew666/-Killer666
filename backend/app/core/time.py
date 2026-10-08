from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite não preserva tzinfo; timestamps persistidos são sempre UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def elapsed_days(start: datetime | None, end: datetime) -> float:
    if start is None:
        return 0.0
    return max(0.0, (as_utc(end) - as_utc(start)).total_seconds() / 86400)
