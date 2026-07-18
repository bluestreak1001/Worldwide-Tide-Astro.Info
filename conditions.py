"""
conditions.py - Boating-Day & Fishing-Day scoring for Worldwide-Tide-Astro.Info

Turns the raw data the station already gathers (marine sea-state, wind, tides,
barometric trend, solunar periods, water temp) into two 0-10 scores with plain-
language verdicts:

  * BOATING DAY - is it safe/comfortable to be on this water today?
  * FISHING DAY - are the fish likely to be feeding?

Both are WATERS-AWARE. A stiff SW breeze that shuts down the open ocean off
Montauk is a fine day inside Great South Bay, and an inlet gets dangerous on a
wind-against-tide that the Sound would shrug off. The `waters` class selects the
tolerance thresholds and tailors the notes.

Pure computation - feed it a plain dict, get a plain dict back. No network or
hardware here, so it runs and unit-tests identically on CPython and MicroPython.
"""

# Waters classes and their character.
WATERS_LABELS = {
    "north-shore":      "LI Sound / North Shore",
    "south-shore-bays": "South Shore Bays",
    "inlets":           "Inlets",
    "ocean":            "Ocean / Beaches",
    "peconics":         "Peconics / The Forks",
    "unclassified":     "Open water",
}

# Per-class thresholds: gust (mph) and wave (ft) at which conditions turn
# (caution, danger). Protected waters tolerate more wind but have no ocean
# swell; exposed waters turn on smaller seas.
#                       gust_caution gust_danger wave_caution wave_danger
_THRESH = {
    "ocean":            (20, 29, 4.0, 6.0),
    "inlets":           (18, 28, 3.0, 5.0),
    "north-shore":      (23, 32, 3.0, 5.0),
    "peconics":         (23, 32, 2.5, 4.0),
    "south-shore-bays": (25, 34, 2.0, 3.5),
    "unclassified":     (21, 30, 3.0, 5.0),
}


# Name keywords -> waters class (mirrors the scraper's gazetteer). Order
# matters: earlier classes win, so inlets/ocean beat the bays.
_WATERS_KEYWORDS = [
    ("inlets", ["inlet"]),
    ("ocean", ["montauk", "ocean", "atlantic", "offshore", "fire island",
               "robert moses", "democrat point", "rockaway beach"]),
    ("peconics", ["southold", "greenport", "orient", "peconic", "gardiners",
                  "shelter island", "sag harbor", "noyack", "riverhead",
                  "mattituck", "cutchogue", "jamesport", "hampton bays",
                  "north fork"]),
    ("south-shore-bays", ["great south bay", "south bay", "moriches",
                          "shinnecock bay", "jamaica bay", "sheepshead",
                          "brooklyn", "oakdale", "babylon", "bay shore",
                          "freeport", "captree", "point lookout", "merrick",
                          "amityville", "islip", "patchogue", "bellport"]),
    ("north-shore", ["port washington", "northport", "huntington",
                     "port jefferson", "smithtown", "stony brook",
                     "mount sinai", "sea cliff", "glen cove", "oyster bay",
                     "cold spring", "long island sound", "the sound",
                     "manhasset", "roslyn", "bayville", "kings park",
                     "nissequogue", "sound"]),
]


def guess_waters(name="", lat=None, lon=None):
    """
    Classify a harbor into a Long Island waters class from its place name,
    with a coarse lat/lon fallback for the LI region. Returns 'unclassified'
    for places we can't tie to LI (the station still works worldwide - it just
    won't have LI report/tuning).
    """
    n = (name or "").lower()
    for cls, keys in _WATERS_KEYWORDS:
        for k in keys:
            if k in n:
                return cls
    # Coarse geographic fallback within the Long Island region.
    if lat is not None and lon is not None:
        if 40.5 <= lat <= 41.3 and -74.1 <= lon <= -71.8:
            if lat >= 40.9:              # north side -> Sound
                return "north-shore"
            if lon <= -73.3:             # western south shore -> bays
                return "south-shore-bays"
            if lon >= -72.5:             # east end -> Peconics/Forks
                return "peconics"
            return "south-shore-bays"
    return "unclassified"


def _sev(x, caution, danger):
    """Severity 0..1: ~0 well below caution, 0.35 at caution, 1.0 at danger."""
    if x is None:
        return 0.0
    if caution <= 0:
        return 0.0
    if x <= caution:
        return 0.35 * (x / caution)
    if x >= danger:
        return 1.0
    return 0.35 + 0.65 * (x - caution) / (danger - caution)


def _weather_penalty(weather_code, precip_in):
    """0..3 penalty from precipitation / storms / fog (WMO codes)."""
    c = weather_code or 0
    pen = 0.0
    if c >= 95:                 # thunderstorm
        pen = 3.0
    elif c >= 80:               # rain/snow showers
        pen = 1.6
    elif c >= 71:               # snow
        pen = 2.2
    elif c >= 61:               # rain
        pen = 1.4
    elif c >= 51:               # drizzle
        pen = 0.7
    elif c >= 45:               # fog
        pen = 1.2
    if precip_in and precip_in >= 0.1:
        pen = max(pen, 1.2)
    return pen


def _boating_label(score):
    if score >= 9:   return "Excellent"
    if score >= 7:   return "Good"
    if score >= 5:   return "Fair"
    if score >= 3:   return "Caution"
    return "Stay In"


def score_boating(inp):
    waters = inp.get("waters", "unclassified")
    gc, gd, wc, wd = _THRESH.get(waters, _THRESH["unclassified"])
    gust = inp.get("gust_mph")
    if gust is None:
        gust = inp.get("wind_mph")
    wave = inp.get("wave_ft")

    sev_wind = _sev(gust, gc, gd)
    sev_wave = _sev(wave, wc, wd) if wave is not None else 0.0
    wx_pen = _weather_penalty(inp.get("weather_code"), inp.get("precip_in"))

    score = 10.0 - 5.0 * sev_wind - 4.0 * sev_wave - wx_pen
    score = max(0.0, min(10.0, score))

    flags = []
    if sev_wind >= 1.0 or sev_wave >= 1.0:
        flags.append("SMALL CRAFT conditions")
    elif sev_wind >= 0.6 or sev_wave >= 0.6:
        flags.append("Building - watch the forecast")
    if waters == "inlets" and (gust or 0) >= 18 and inp.get("tide_moving", 0) >= 0.4:
        flags.append("Wind-over-tide: steep inlet chop likely")
    if (inp.get("weather_code") or 0) >= 95:
        flags.append("Thunderstorms - stay off the water")

    bits = []
    if gust is not None:
        bits.append("wind/gust %d mph" % int(round(gust)))
    if wave is not None:
        bits.append("seas %.1f ft" % wave)
    detail = ", ".join(bits)
    return {"score": round(score, 1), "label": _boating_label(score),
            "flags": flags, "detail": detail}


def _pressure_factor(arrow):
    # Fish often feed hard on a falling glass ahead of a front; a fast rise
    # behind one tends to shut them off.
    return {"v": 0.9, "vv": 0.7, "-": 0.6, "^": 0.5,
            "^^": 0.3, "?": 0.55, None: 0.55}.get(arrow, 0.55)


def _wind_factor(wind_mph):
    if wind_mph is None:
        return 0.6
    if wind_mph < 3:            # dead calm
        return 0.6
    if wind_mph <= 15:          # light-moderate: a fishy ripple
        return 0.9
    if wind_mph <= 22:
        return 0.6
    return 0.3                  # too much to fish well


def _temp_factor(water_temp_f):
    # Broad LI inshore feeding window ~ 55-74 F.
    if water_temp_f is None:
        return 0.6
    t = water_temp_f
    if 58 <= t <= 72:
        return 0.9
    if 54 <= t <= 76:
        return 0.7
    if 48 <= t <= 80:
        return 0.5
    return 0.35


def tide_movement(events, now_epoch):
    """
    From tide extremes (each {type, epoch}) find whether the tide is rising or
    falling now and how hard it's running. Returns {dir, moving 0..1,
    mins_to_next, next_type} or None if it can't be determined.
    'moving' peaks (1.0) at mid-tide max current and is ~0 at slack.
    """
    if not events:
        return None
    try:
        import math
    except ImportError:
        math = None
    evs = sorted(events, key=lambda e: e.get("epoch", 0))
    prev = nxt = None
    for e in evs:
        ep = e.get("epoch", 0)
        if ep <= now_epoch:
            prev = e
        elif nxt is None:
            nxt = e
    if prev is None or nxt is None:
        return None
    interval = nxt["epoch"] - prev["epoch"]
    if interval <= 0:
        return None
    pos = (now_epoch - prev["epoch"]) / interval        # 0..1 between slacks
    if math:
        moving = math.sin(pos * math.pi)
    else:
        moving = 1.0 - abs(2.0 * pos - 1.0)             # triangular fallback
    nxt_type = nxt.get("type", "").strip().upper()
    rising = nxt_type.startswith("HIGH")
    return {"dir": "rising" if rising else "falling",
            "moving": round(moving, 2),
            "mins_to_next": int((nxt["epoch"] - now_epoch) / 60),
            "next_type": "HIGH" if rising else "LOW"}


def _fishing_label(score):
    if score >= 8:   return "Excellent"
    if score >= 6.5: return "Very Good"
    if score >= 5:   return "Good"
    if score >= 3.5: return "Fair"
    return "Slow"


def score_fishing(inp):
    sol = inp.get("solunar") or {}
    sol_score = sol.get("score", 40) / 100.0
    press = _pressure_factor(inp.get("pressure_arrow"))
    wind = _wind_factor(inp.get("wind_mph"))
    temp = _temp_factor(inp.get("water_temp_f"))

    tide = inp.get("tide")
    if tide and "moving" in tide:
        tide_f = 0.4 + 0.6 * tide["moving"]
    else:
        tide_f = 0.6

    score10 = 10.0 * (0.35 * sol_score + 0.20 * press +
                      0.20 * tide_f + 0.15 * wind + 0.10 * temp)
    score10 = max(0.0, min(10.0, score10))

    # Best window: the next/active solunar period, ideally overlapping moving
    # water and low light.
    window = None
    active = sol.get("active")
    nxt = sol.get("next")
    if active:
        window = ("Now: %s feeding period" %
                  ("MAJOR" if active["kind"] == "major" else "minor"))
    elif nxt:
        from_h = nxt.get("center")
        tag = "MAJOR" if nxt["kind"] == "major" else "minor"
        try:
            import solunar
            window = "Next: %s at %s" % (tag, solunar.fmt_hours(from_h))
        except Exception:
            window = "Next: %s" % tag

    notes = []
    if tide and "dir" in tide:
        notes.append("%s tide" % tide["dir"] +
                     (", running" if tide.get("moving", 0) > 0.5 else ", slack"))
    if inp.get("pressure_arrow") in ("v", "vv"):
        notes.append("falling barometer - feed ahead of the change")
    elif inp.get("pressure_arrow") in ("^^",):
        notes.append("pressure spiking - bite may be tough")

    return {"score": round(score10, 1), "label": _fishing_label(score10),
            "window": window, "notes": notes,
            "components": {"solunar": round(sol_score, 2),
                           "pressure": press, "tide": round(tide_f, 2),
                           "wind": wind, "temp": temp}}


def assess(inp):
    """Top-level: score both, add a one-line combined verdict."""
    boating = score_boating(inp)
    fishing = score_fishing(inp)
    waters = inp.get("waters", "unclassified")

    b, f = boating["score"], fishing["score"]
    if b < 3:
        verdict = "Rough - not a day to head out."
    elif f >= 6.5 and b >= 7:
        verdict = "Prime day - go fish."
    elif f >= 6.5 and b >= 5:
        verdict = "Good bite, but mind the conditions."
    elif b >= 7 and f < 5:
        verdict = "Nice day on the water; fishing may be slow."
    elif b >= 5:
        verdict = "Workable day - pick your spots."
    else:
        verdict = "Marginal - short window at best."

    return {
        "waters": waters,
        "waters_label": WATERS_LABELS.get(waters, "Open water"),
        "boating": boating,
        "fishing": fishing,
        "verdict": verdict,
    }
