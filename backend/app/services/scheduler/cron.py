"""Cron helpers: validation and next-occurrence computation (timezone aware)."""
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from croniter import croniter

from app.config import get_settings


def validate_timezone(tz: str) -> Optional[str]:
    """Return an error message, or None if the timezone is valid."""
    try:
        ZoneInfo(tz)
        return None
    except Exception:
        return f"Unknown timezone '{tz}'"


def validate_cron(expr: str) -> Optional[str]:
    """Return an error message, or None if the expression is valid and allowed."""
    expr = (expr or "").strip()
    if len(expr.split()) != 5:
        return "Cron expression must have exactly 5 fields (minute hour day-of-month month day-of-week)"
    if not croniter.is_valid(expr):
        return f"Invalid cron expression '{expr}'"

    min_minutes = get_settings().SCHEDULER_MIN_INTERVAL_MINUTES
    try:
        it = croniter(expr, datetime(2024, 1, 1, tzinfo=timezone.utc))
        previous = it.get_next(datetime)
        smallest_gap = None
        for _ in range(6):
            current = it.get_next(datetime)
            gap = (current - previous).total_seconds()
            smallest_gap = gap if smallest_gap is None else min(smallest_gap, gap)
            previous = current
        if smallest_gap is not None and smallest_gap < min_minutes * 60:
            return f"Minimum allowed interval is {min_minutes} minutes"
    except Exception as exc:  # croniter raises various exception types
        return f"Invalid cron expression: {exc}"
    return None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def next_run_after(expr: str, tz: str, after: datetime) -> datetime:
    """Next occurrence strictly after `after`, returned as an aware UTC datetime."""
    zone = ZoneInfo(tz)
    base = _as_utc(after).astimezone(zone)
    nxt = croniter(expr.strip(), base).get_next(datetime)
    return _as_utc(nxt)


def upcoming(expr: str, tz: str, count: int = 5, after: Optional[datetime] = None) -> List[datetime]:
    """Next `count` occurrences as aware UTC datetimes."""
    zone = ZoneInfo(tz)
    start = _as_utc(after or datetime.now(timezone.utc)).astimezone(zone)
    it = croniter(expr.strip(), start)
    return [_as_utc(it.get_next(datetime)) for _ in range(count)]
