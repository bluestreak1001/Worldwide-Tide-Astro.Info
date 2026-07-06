"""
tides.py - WorldTides API wrapper for Pico W
API docs: https://www.worldtides.info/apidocs
"""

import urequests
try:
    import secrets
    WORLDTIDES_KEY = secrets.WORLDTIDES_KEY
except ImportError:
    raise RuntimeError("secrets.py not found - copy secrets_template.py to secrets.py and fill in your credentials")
import utime

EXTREMES_URL = "https://www.worldtides.info/api/v3"

def _epoch_to_hm(epoch_sec, tz_offset_hours=0):
    local = epoch_sec + tz_offset_hours * 3600
    t = utime.localtime(local)
    return f"{t[3]:02d}:{t[4]:02d}"

def _epoch_to_date(epoch_sec, tz_offset_hours=0):
    local = epoch_sec + tz_offset_hours * 3600
    t = utime.localtime(local)
    return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"

def get_tide_data(lat, lon, tz_offset=0, days=1):
    now = utime.time()
    t = utime.localtime(now)
    today_midnight = now - (t[3]*3600 + t[4]*60 + t[5])
    length_sec = days * 86400
    url = (f"{EXTREMES_URL}"
           f"?extremes"
           f"&lat={lat:.5f}"
           f"&lon={lon:.5f}"
           f"&start={today_midnight}"
           f"&length={length_sec}"
           f"&datum=CD"
           f"&key={WORLDTIDES_KEY}")
    print(f"[Tides] Fetching from WorldTides API...")
    try:
        r = urequests.get(url, timeout=12)
        data = r.json()
        r.close()
    except Exception as e:
        raise RuntimeError(f"WorldTides request failed: {e}")
    if "error" in data:
        raise RuntimeError(f"WorldTides API error: {data['error']}")
    status = data.get("status", 200)
    if status != 200:
        raise RuntimeError(f"WorldTides returned status {status}: {data.get('reason', 'unknown')}")
    extremes = data.get("extremes", [])
    if not extremes:
        return []
    events = []
    for ex in extremes:
        epoch = ex.get("dt", 0)
        height_m = ex.get("height", 0.0)
        height_ft = height_m * 3.28084
        tide_type = ex.get("type", "?").upper()
        if tide_type.startswith("H"):
            label = "HIGH TIDE"
        elif tide_type.startswith("L"):
            label = "LOW TIDE "
        else:
            label = tide_type
        events.append({
            "type":      label,
            "time":      _epoch_to_hm(epoch, tz_offset),
            "date":      _epoch_to_date(epoch, tz_offset),
            "height_m":  height_m,
            "height_ft": height_ft,
            "epoch":     epoch,
        })
    events.sort(key=lambda e: e["epoch"])
    return events

def get_tide_data_twoday(lat, lon, tz_offset=0):
    return get_tide_data(lat, lon, tz_offset, days=2)
