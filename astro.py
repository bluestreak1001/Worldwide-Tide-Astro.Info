"""
astro.py - Astronomical data for Pico W station
Solar data: sunrise-sunset.org API
Moon rise/set: Meeus-based calculation (no API needed)
Moon phase: Meeus simple formula
"""

import math

def _fmt_hm(hour_float, tz_offset=0):
    if hour_float is None:
        return "--:--"
    total = (hour_float + tz_offset) % 24
    h = int(total)
    m = int((total - h) * 60 + 0.5)
    if m == 60:
        h = (h + 1) % 24
        m = 0
    return f"{h:02d}:{m:02d}"

def _fmt_duration(rise_h, set_h):
    if rise_h is None or set_h is None:
        return "--"
    diff = set_h - rise_h
    if diff < 0:
        diff += 24
    h = int(diff)
    m = int((diff - h) * 60 + 0.5)
    return f"{h}h {m:02d}m"

def _iso_to_decimal_hours(iso_str):
    if not iso_str or iso_str == "1970-01-01T00:00:00+00:00":
        return None
    try:
        if "T" in iso_str:
            time_part = iso_str.split("T")[1][:8]
        else:
            time_part = iso_str[:8]
        parts = time_part.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return h + m / 60.0 + s / 3600.0
    except Exception:
        return None

_PHASE_TABLE = [
    (0.0,  0.02, "New Moon",        "🌑"),
    (0.02, 0.24, "Waxing Crescent", "🌒"),
    (0.24, 0.26, "First Quarter",   "🌓"),
    (0.26, 0.49, "Waxing Gibbous",  "🌔"),
    (0.49, 0.51, "Full Moon",       "🌕"),
    (0.51, 0.74, "Waning Gibbous",  "🌖"),
    (0.74, 0.76, "Last Quarter",    "🌗"),
    (0.76, 0.98, "Waning Crescent", "🌘"),
    (0.98, 1.01, "New Moon",        "🌑"),
]

def _phase_name_icon(phase_frac):
    for lo, hi, name, icon in _PHASE_TABLE:
        if lo <= phase_frac < hi:
            return name, icon
    return "Unknown", "🌑"

def _moon_phase_calc(year, month, day):
    jd = (367 * year
          - int(7 * (year + int((month + 9) / 12)) / 4)
          + int(275 * month / 9)
          + day + 1721013.5)
    age_days = (jd - 2451550.1) % 29.53059
    phase_frac = age_days / 29.53059
    illum = int(round(50 * (1 - math.cos(phase_frac * 2 * math.pi))))
    return phase_frac, illum

def _calc_moonrise_moonset(lat, lon, year, month, day):
    def jd(y, m, d):
        if m <= 2:
            y -= 1
            m += 12
        A = int(y / 100)
        B = 2 - A + int(A / 4)
        return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5

    def norm(x):
        return x - 360.0 * math.floor(x / 360.0)

    def rev24(x):
        return x - 24.0 * math.floor(x / 24.0)

    rad = math.pi / 180.0
    deg = 180.0 / math.pi

    def moon_ra_dec(jd_val):
        T = (jd_val - 2451545.0) / 36525.0
        L0 = norm(218.3165 + 481267.8813 * T)
        M  = norm(357.5291 + 35999.0503  * T)
        Mp = norm(134.9634 + 477198.8676 * T)
        D  = norm(297.8502 + 445267.1115 * T)
        F  = norm(93.2721  + 483202.0175 * T)
        lam = (L0
               + 6.289 * math.sin(Mp * rad)
               - 1.274 * math.sin((2*D - Mp) * rad)
               + 0.658 * math.sin(2*D * rad)
               - 0.186 * math.sin(M * rad)
               - 0.059 * math.sin((2*D - 2*Mp) * rad)
               - 0.057 * math.sin((2*D - M - Mp) * rad)
               + 0.053 * math.sin((2*D + Mp) * rad)
               + 0.046 * math.sin((2*D - M) * rad)
               + 0.041 * math.sin((Mp - M) * rad)
               - 0.035 * math.sin(D * rad)
               - 0.031 * math.sin((Mp + M) * rad)
               - 0.015 * math.sin((2*F - 2*D) * rad)
               + 0.011 * math.sin((2*D - M + Mp) * rad))
        beta = (5.128 * math.sin(F * rad)
                + 0.281 * math.sin((Mp + F) * rad)
                - 0.278 * math.sin((2*D - F) * rad)
                - 0.173 * math.sin((Mp - F) * rad)
                - 0.055 * math.sin((2*D - Mp + F) * rad)
                - 0.046 * math.sin((2*D - Mp - F) * rad)
                + 0.033 * math.sin((Mp + 2*D + F) * rad)
                + 0.017 * math.sin((2*Mp + F) * rad))
        eps = 23.439 - 0.013 * T
        lam_r  = lam * rad
        beta_r = beta * rad
        eps_r  = eps * rad
        ra = math.atan2(math.sin(lam_r) * math.cos(eps_r)
                        - math.tan(beta_r) * math.sin(eps_r),
                        math.cos(lam_r)) * deg
        ra = norm(ra) / 15.0
        dec = math.asin(math.sin(beta_r) * math.cos(eps_r)
                        + math.cos(beta_r) * math.sin(eps_r)
                        * math.sin(lam_r)) * deg
        return ra, dec

    def gmst0(jd_val):
        T = (jd_val - 2451545.0) / 36525.0
        return norm(100.4606184 + 36000.77004 * T + 0.000387933 * T * T)

    jd0  = jd(year, month, day)
    lat_r = lat * rad
    lon_w = -lon
    h0    = 0.7275 * 0.9507 - 0.34

    ra0, dec0 = moon_ra_dec(jd0 - 1)
    ra1, dec1 = moon_ra_dec(jd0)
    ra2, dec2 = moon_ra_dec(jd0 + 1)
    theta0    = gmst0(jd0)

    cos_H = ((math.sin(h0 * rad) - math.sin(lat_r) * math.sin(dec1 * rad))
             / (math.cos(lat_r) * math.cos(dec1 * rad)))

    if cos_H < -1.0 or cos_H > 1.0:
        return None, None

    H0 = math.acos(cos_H) * deg

    m_transit = norm(ra1 * 15 + lon_w - theta0) / 360.0
    m_rise    = m_transit - H0 / 360.0
    m_set     = m_transit + H0 / 360.0

    def interp3(y1, y2, y3, n):
        a = y2 - y1
        b = y3 - y2
        c = b - a
        return y2 + n * (a + b + n * c) / 2.0

    for _ in range(2):
        for which, m_val in [("rise", m_rise), ("set", m_set)]:
            n     = m_val + lon_w / 360.0
            ra_i  = interp3(ra0,  ra1,  ra2,  n)
            dec_i = interp3(dec0, dec1, dec2, n)
            theta_loc = norm(theta0 + 360.985647 * m_val) - lon_w
            H     = theta_loc - ra_i * 15.0
            H_r   = H * rad
            dec_r = dec_i * rad
            alt   = math.asin(math.sin(lat_r) * math.sin(dec_r)
                              + math.cos(lat_r) * math.cos(dec_r)
                              * math.cos(H_r)) * deg
            dm = (alt - h0) / (360.0 * math.cos(dec_r)
                               * math.cos(lat_r) * math.sin(H_r))
            if which == "rise":
                m_rise = m_val + dm
            else:
                m_set  = m_val + dm

    return rev24(m_rise * 24.0), rev24(m_set * 24.0)

def get_astro_data(lat, lon, year, month, day, tz_offset=0):
    try:
        from sun_moon import Sun, Moon
        from moonphase import MoonPhase
        sun  = Sun(lat, lon)
        moon = Moon(lat, lon)
        mp   = MoonPhase()
        sun.calc(year, month, day)
        moon.calc(year, month, day)
        mp.calc(year, month, day)
        if hasattr(mp, "phase"):
            phase_frac = float(mp.phase)
        elif hasattr(mp, "illumination"):
            phase_frac = float(mp.illumination) / 100.0
        else:
            phase_frac = 0.0
        illum = int(round(float(mp.illumination))) if hasattr(mp, "illumination") \
                else int(round(phase_frac * 100))
        phase_name, phase_icon = _phase_name_icon(phase_frac)
        if hasattr(mp, "phase_name") and mp.phase_name:
            phase_name = mp.phase_name
        return {
            "sunrise":      _fmt_hm(getattr(sun,  "rise", None), tz_offset),
            "sunset":       _fmt_hm(getattr(sun,  "set",  None), tz_offset),
            "solar_noon":   _fmt_hm(getattr(sun,  "noon", None), tz_offset),
            "day_length":   _fmt_duration(getattr(sun,  "rise", None),
                                          getattr(sun,  "set",  None)),
            "moonrise":     _fmt_hm(getattr(moon, "rise", None), tz_offset),
            "moonset":      _fmt_hm(getattr(moon, "set",  None), tz_offset),
            "phase_name":   phase_name,
            "illumination": illum,
            "phase_icon":   phase_icon,
        }
    except ImportError:
        pass

    import urequests
    sun_url = (f"https://api.sunrise-sunset.org/json"
               f"?lat={lat}&lng={lon}"
               f"&date={year:04d}-{month:02d}-{day:02d}"
               f"&formatted=0")
    print("[Astro] Fetching sunrise-sunset.org...")
    r = urequests.get(sun_url, timeout=10)
    sun_data = r.json().get("results", {})
    r.close()

    sunrise_h = _iso_to_decimal_hours(sun_data.get("sunrise"))
    sunset_h  = _iso_to_decimal_hours(sun_data.get("sunset"))
    noon_h    = _iso_to_decimal_hours(sun_data.get("solar_noon"))

    print("[Astro] Calculating moonrise/moonset...")
    mrise_h, mset_h = _calc_moonrise_moonset(lat, lon, year, month, day)

    phase_frac, illum = _moon_phase_calc(year, month, day)
    phase_name, phase_icon = _phase_name_icon(phase_frac)

    return {
        "sunrise":      _fmt_hm(sunrise_h, tz_offset),
        "sunset":       _fmt_hm(sunset_h,  tz_offset),
        "solar_noon":   _fmt_hm(noon_h,    tz_offset),
        "day_length":   _fmt_duration(sunrise_h, sunset_h),
        "moonrise":     _fmt_hm(mrise_h,   tz_offset),
        "moonset":      _fmt_hm(mset_h,    tz_offset),
        "phase_name":   phase_name,
        "illumination": illum,
        "phase_icon":   phase_icon,
    }

def get_forecast(lat, lon):
    import urequests
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=" + str(round(lat, 4)) +
           "&longitude=" + str(round(lon, 4)) +
           "&daily=temperature_2m_max,temperature_2m_min,"
           "precipitation_probability_max,windspeed_10m_max,"
           "winddirection_10m_dominant,weathercode"
           "&temperature_unit=fahrenheit"
           "&windspeed_unit=mph"
           "&timezone=auto"
           "&forecast_days=2")
    print("[Forecast] Fetching Open-Meteo...")
    r = urequests.get(url, timeout=12)
    data = r.json()
    r.close()
    daily = data.get("daily", {})
    codes = daily.get("weathercode", [0, 0])

    def wcode(c):
        if c == 0:    return "Clear Sky"
        elif c <= 2:  return "Partly Cloudy"
        elif c == 3:  return "Overcast"
        elif c <= 49: return "Foggy"
        elif c <= 59: return "Drizzle"
        elif c <= 69: return "Rain"
        elif c <= 79: return "Snow"
        elif c <= 82: return "Rain Showers"
        elif c <= 86: return "Snow Showers"
        elif c <= 99: return "Thunderstorm"
        return "Unknown"

    def wdir(deg):
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[int((deg + 22.5) / 45) % 8]

    dates = daily.get("time", [])
    hi    = daily.get("temperature_2m_max", [])
    lo    = daily.get("temperature_2m_min", [])
    pop   = daily.get("precipitation_probability_max", [])
    wind  = daily.get("windspeed_10m_max", [])
    wdir2 = daily.get("winddirection_10m_dominant", [])

    result = []
    for i in range(min(2, len(dates))):
        result.append({
            "date":       dates[i]            if i < len(dates) else "--",
            "high":       str(round(hi[i]))   if i < len(hi)    else "--",
            "low":        str(round(lo[i]))   if i < len(lo)    else "--",
            "conditions": wcode(codes[i])     if i < len(codes) else "--",
            "precip":     str(pop[i])         if i < len(pop)   else "--",
            "wind":       str(round(wind[i])) if i < len(wind)  else "--",
            "wind_dir":   wdir(wdir2[i])      if i < len(wdir2) else "--",
        })
    return result

def get_current(lat, lon):
    """
    Current atmospheric conditions from Open-Meteo (no key, no sensor needed).
    Supplies wind/gust for the boating score and works even before a BME688 is
    wired in. Returns {wind_mph, gust_mph, wind_dir, weather_code, precip_in,
    air_temp_f, humidity} or None.
    """
    import urequests
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=" + str(round(lat, 4)) +
           "&longitude=" + str(round(lon, 4)) +
           "&current=temperature_2m,relative_humidity_2m,precipitation,"
           "weather_code,wind_speed_10m,wind_gusts_10m,wind_direction_10m"
           "&temperature_unit=fahrenheit&wind_speed_unit=mph"
           "&precipitation_unit=inch&timezone=auto")
    print("[Current] Fetching Open-Meteo current...")
    try:
        r = urequests.get(url, timeout=12)
        data = r.json()
        r.close()
    except Exception as e:
        print("[Current] " + str(e))
        return None
    c = data.get("current", {})
    if not c:
        return None

    def wdir(deg):
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[int((deg + 22.5) / 45) % 8]

    wd = c.get("wind_direction_10m")
    return {
        "wind_mph":     round(c.get("wind_speed_10m", 0)),
        "gust_mph":     round(c.get("wind_gusts_10m", 0)),
        "wind_dir":     wdir(wd) if wd is not None else "--",
        "weather_code": c.get("weather_code", 0),
        "precip_in":    round(c.get("precipitation", 0), 2),
        "air_temp_f":   round(c.get("temperature_2m", 0), 1),
        "humidity":     round(c.get("relative_humidity_2m", 0)),
    }


def get_marine(lat, lon):
    import urequests
    url = ("https://marine-api.open-meteo.com/v1/marine"
           "?latitude=" + str(round(lat, 4)) +
           "&longitude=" + str(round(lon, 4)) +
           "&current=sea_surface_temperature,wave_height,wave_period"
           "&temperature_unit=fahrenheit")
    print("[Marine] Fetching Open-Meteo Marine...")
    r = urequests.get(url, timeout=12)
    data = r.json()
    r.close()
    current = data.get("current", {})
    sst = current.get("sea_surface_temperature", None)
    wh  = current.get("wave_height", None)
    wp  = current.get("wave_period", None)
    if sst is None:
        return None
    sst_c = round((sst - 32) * 5 / 9, 1)
    return {
        "water_temp_f":  round(sst, 1),
        "water_temp_c":  sst_c,
        "wave_height_m": round(wh, 2) if wh is not None else None,
        "wave_period":   round(wp, 1) if wp is not None else None,
    }
