"""Expand recurring local shifts and schedule on an absolute UTC minute axis."""

from datetime import datetime, time, timedelta, timezone
from math import ceil, floor, isfinite
from zoneinfo import ZoneInfo


class SchedulingError(ValueError):
    """A preflight or bounded calendar failure."""

    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def round_duration(minutes, tick):
    if type(tick) is not int or not 1 <= tick <= 1440:
        raise ValueError("Tick must be an integer between 1 and 1440 minutes.")
    if type(minutes) not in (int, float) or not isfinite(minutes) or minutes < 0:
        raise ValueError("Duration or lag must be a finite nonnegative minute value.")
    return ceil(round(minutes / tick, 10)) * tick


def _localize(value, zone):
    if value.tzinfo is not None:
        return value.astimezone(zone)
    folds = [value.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = {a.astimezone(timezone.utc) for a in folds
             if a.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == value}
    if len(valid) != 1:
        raise SchedulingError("AMBIGUOUS_LOCAL_TIME", f"Use an explicit offset for {value} in {zone.key}.")
    return valid.pop().astimezone(zone)


def parse_minute(value, zone, tick=1, *, upper=False):
    instant = _localize(datetime.fromisoformat(value), zone)
    rounded = floor if upper else ceil
    return rounded(instant.timestamp() / 60 / tick) * tick


def display(minute, zone):
    return datetime.fromtimestamp(minute * 60, zone).isoformat(timespec="minutes")


def _wall(value):
    result = time.fromisoformat(value)
    if result.tzinfo is not None or result.second or result.microsecond:
        raise ValueError("Working window boundaries must be local HH:MM.")
    return result


def build_windows(calendar, start, horizon, tick, allowed_hours=None):
    """Return merged, nonoverlapping intervals with availability rounded inward."""
    zone = ZoneInfo(calendar["timezone"])
    weekly = {day: [] for day in range(1, 8)}
    for item in calendar["working_windows"]:
        if type(item["weekday"]) is not int or item["weekday"] not in weekly:
            raise ValueError("Invalid working calendar weekday.")
        weekly[item["weekday"]].append((_wall(item["start"]), _wall(item["end"])))
    exceptions = calendar.get("date_exceptions", [])
    overrides = dict(calendar.get("date_overrides", {}))
    for day in exceptions:
        if day in overrides:
            raise ValueError(f"Ambiguous calendar exception: {day}.")
        overrides[day] = []
    for day in overrides:
        datetime.fromisoformat(day).date()
    restriction = [tuple(_wall(v) for v in pair) for pair in allowed_hours] if allowed_hours is not None else None
    ranges = []
    start_day = datetime.fromtimestamp(start * 60, zone).date()
    end_day = datetime.fromtimestamp(horizon * 60, zone).date()
    for offset in range((end_day - start_day).days + 1):
        day = start_day + timedelta(days=offset)
        pattern = ([( _wall(row["start"]), _wall(row["end"])) for row in overrides[day.isoformat()]]
                   if day.isoformat() in overrides else weekly[day.isoweekday()])
        for a, b in pattern:
            if a >= b:
                raise ValueError("Working windows must end later on the same local date.")
            if restriction is not None and any(c >= d for c, d in restriction):
                raise ValueError("Invalid activity-specific working window.")
            for left, right in ([(max(a, c), min(b, d)) for c, d in restriction]
                                if restriction is not None else [(a, b)]):
                if left >= right:
                    continue
                first = max(start, parse_minute(datetime.combine(day, left).isoformat(), zone, tick))
                last = min(horizon, parse_minute(datetime.combine(day, right).isoformat(), zone, tick, upper=True))
                if first < last:
                    ranges.append((first, last))
    merged = []
    for first, last in sorted(ranges):
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    return tuple(merged)


def fit_work(windows, bound, duration, *, split=False, backward=False):
    """Fit work against the same window map in either direction."""
    if not windows or (not split and max(b - a for a, b in windows) < duration):
        raise SchedulingError("NO_FIT", "No available uninterrupted work window fits the duration.")
    segments = []
    remaining = duration
    candidates = reversed(windows) if backward else windows
    for left, right in candidates:
        if backward:
            right = min(right, bound)
        else:
            left = max(left, bound)
        space = right - left
        if space <= 0 or (not split and space < remaining):
            continue
        amount = min(space, remaining)
        segments.append((right - amount, right) if backward else (left, left + amount))
        remaining -= amount
        if not remaining:
            return list(reversed(segments)) if backward else segments
    raise SchedulingError("HORIZON_EXHAUSTED", "The bounded calendar has insufficient available work time.")
