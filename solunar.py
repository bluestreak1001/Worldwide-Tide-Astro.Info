"""
solunar.py - Solunar feeding-period model for Worldwide-Tide-Astro.Info

Solunar theory (John Alden Knight, 1926): fish and game feed most heavily
around the moon's transit (directly overhead) and anti-transit (underfoot) -
the two MAJOR periods - and around moonrise and moonset - the two MINOR
periods. The effect is amplified near the new and full moon, when the sun and
moon pull together.

This module is pure computation: no network, no hardware, no imports beyond
what MicroPython ships. Feed it the moonrise/moonset times and illumination
that astro.get_astro_data() already produces, plus the current local time.
Because it takes plain values, it runs and unit-tests identically on CPython.
"""

MAJOR_HALF = 1.0    # major feeding window is center +/- 1.0 h
MINOR_HALF = 0.75   # minor feeding window is center +/- 45 min


def _hm_to_hours(hm):
    """'HH:MM' -> float hours, or None."""
    if not hm or ":" not in hm:
        return None
    try:
        h, m = hm.split(":")
        return int(h) + int(m) / 60.0
    except Exception:
        return None


def fmt_hours(h):
    """float hours -> 'HH:MM' (wraps at 24)."""
    h = h % 24
    hh = int(h)
    mm = int(round((h - hh) * 60))
    if mm == 60:
        hh = (hh + 1) % 24
        mm = 0
    return "%02d:%02d" % (hh, mm)


def _circ_mid(a, b):
    """Circular midpoint of two hours, treating b as occurring after a."""
    if b < a:
        b += 24
    return ((a + b) / 2.0) % 24


def _in_window(now_h, start, end):
    if start <= end:
        return start <= now_h <= end
    return now_h >= start or now_h <= end     # window wraps midnight


def _dist(now_h, center):
    d = abs((now_h - center) % 24)
    return min(d, 24 - d)


def periods(moonrise_h, moonset_h):
    """List of feeding periods {kind, center, start, end} for the day."""
    raw = []
    if moonrise_h is not None:
        raw.append(("minor", moonrise_h))
    if moonset_h is not None:
        raw.append(("minor", moonset_h))
    if moonrise_h is not None and moonset_h is not None:
        transit = _circ_mid(moonrise_h, moonset_h)
        raw.append(("major", transit))
        raw.append(("major", (transit + 12.0) % 24))
    out = []
    for kind, c in raw:
        half = MAJOR_HALF if kind == "major" else MINOR_HALF
        out.append({"kind": kind, "center": c % 24,
                    "start": (c - half) % 24, "end": (c + half) % 24})
    out.sort(key=lambda p: p["center"])
    return out


def phase_strength(illumination):
    """0..1 amplification: 1.0 at new/full moon, 0.0 at the quarters."""
    if illumination is None:
        return 0.5
    return abs(1.0 - illumination / 50.0)


def _next_period(ps, now_h):
    best, bd = None, 99.0
    for p in ps:
        d = (p["center"] - now_h) % 24
        if 0 < d < bd:
            bd, best = d, p
    return best


def solunar_now(moonrise_hm, moonset_hm, illumination, now_hour, now_min=0):
    """
    Evaluate solunar activity for the current local time.
    Returns dict: score 0..100 (solunar-only), whether a period is active,
    the nearest/next period, phase strength, and the full period list.
    """
    now_h = now_hour + now_min / 60.0
    mr = _hm_to_hours(moonrise_hm)
    ms = _hm_to_hours(moonset_hm)
    ps = periods(mr, ms)

    active, nearest, nd = None, None, 99.0
    for p in ps:
        if _in_window(now_h, p["start"], p["end"]):
            if active is None or p["kind"] == "major":
                active = p
        d = _dist(now_h, p["center"])
        if d < nd:
            nd, nearest = d, p

    strength = phase_strength(illumination)      # 0..1
    if active and active["kind"] == "major":
        prox = 1.0
    elif active:
        prox = 0.72
    elif nearest:
        prox = max(0.0, 0.6 * (1.0 - nd / 3.0))  # decays over ~3 h
        if nearest["kind"] == "minor":
            prox *= 0.85
    else:
        prox = 0.0

    score = int(round(100 * (0.45 * strength + 0.55 * prox)))
    return {
        "score": max(0, min(100, score)),
        "active": active,
        "nearest": nearest,
        "next": _next_period(ps, now_h),
        "strength": round(strength, 2),
        "periods": ps,
    }


def format_periods(ps):
    """['MAJOR 04:12', 'minor 11:30', ...] for display."""
    out = []
    for p in ps:
        tag = "MAJOR" if p["kind"] == "major" else "minor"
        out.append(tag + " " + fmt_hours(p["center"]))
    return out
