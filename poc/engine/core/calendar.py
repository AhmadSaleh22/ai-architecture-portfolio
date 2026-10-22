"""Weekly calendars -> working windows in minutes from t0."""
from datetime import date, datetime, timedelta

DAYNAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _hhmm(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def windows(cal, t0, horizon, startup=0):
    """cal = {weekly: {sun: [["08:00","16:00"], ...]}, closed_dates: [...]}.
    An end <= start crosses midnight. Contiguous windows are merged; startup is cut from each start."""
    closed = {date.fromisoformat(str(d)) for d in cal.get("closed_dates", []) or []}
    raw = []
    day = t0.date() - timedelta(days=1)
    while True:
        base = datetime.combine(day, datetime.min.time())
        if (base - t0).total_seconds() / 60 > horizon:
            break
        if day not in closed:
            for a, b in cal.get("weekly", {}).get(DAYNAMES[day.weekday()], []):
                s, e = _hhmm(a), _hhmm(b)
                if e <= s:
                    e += 1440
                start = int((base - t0).total_seconds() // 60) + s
                raw.append([start, start + e - s])
        day += timedelta(days=1)
    raw.sort()
    merged = []
    for s, e in raw:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out = []
    for s, e in merged:
        s = max(s + startup, 0)
        if e > s:
            out.append((s, min(e, horizon)))
    return [w for w in out if w[1] > w[0]]
