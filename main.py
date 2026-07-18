"""
main.py - Worldwide-Tide-Astro.Info
Astronomical & Tide Station for Raspberry Pi Pico W
Boot sequence:
  1. Connect to WiFi
  2. Sync RTC via NTP
  3. If no saved location, serve web config until user saves one
  4. Web server stays running in background for location changes
  5. Take initial BME688 reading
  6. Timer fires every 15 min to silently log pressure
  7. GP15 (physical Pin 20) button triggers full shell display refresh
"""

import network
import urequests
import utime
import ujson
import machine
from machine import Timer
import gc
from web_config import serve_data_page
from astro import get_astro_data
from tides import get_tide_data
from weather import log_pressure, get_weather, load_log

try:
    import secrets
except ImportError:
    raise RuntimeError("secrets.py not found - copy secrets_template.py to secrets.py and fill in your credentials")

WIFI_SSID         = secrets.WIFI_SSID
WIFI_PASSWORD     = secrets.WIFI_PASSWORD
MANUAL_UTC_OFFSET = -4
CONFIG_FILE       = "config.json"
REFRESH_BTN       = 15
WIFI_TIMEOUT      = 20
LOG_INTERVAL_MS   = 900000

_log_due = False
_cfg     = None
_btn     = None

led = machine.Pin("LED", machine.Pin.OUT)

def led_on():
    led.value(1)

def led_off():
    led.value(0)

def led_blink(times=1, ms=100):
    for _ in range(times):
        led.value(1)
        utime.sleep_ms(ms)
        led.value(0)
        utime.sleep_ms(ms)

def z2(n):
    s = str(int(n))
    return s if len(s) >= 2 else "0" + s

def z4(n):
    s = str(int(n))
    while len(s) < 4:
        s = "0" + s
    return s

def connect_wifi(ssid, password, timeout=WIFI_TIMEOUT):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    print("\n[WiFi] Connecting to '" + ssid + "' ", end="")
    wlan.connect(ssid, password)
    t = 0
    while not wlan.isconnected() and t < timeout:
        print(".", end="")
        led_blink(1, 200)
        t += 1
    if wlan.isconnected():
        print("\n[WiFi] Connected - IP: " + wlan.ifconfig()[0])
        led_blink(3, 100)
    else:
        print("\n[WiFi] FAILED - check SSID / password")
        led_blink(10, 50)
    return wlan

def sync_rtc():
    sources = [
        "http://timeapi.io/api/time/current/zone?timeZone=UTC",
        "http://worldtimeapi.org/api/timezone/Etc/UTC",
    ]
    for url in sources:
        try:
            print("[NTP] Trying " + url)
            r = urequests.get(url, timeout=10)
            data = r.json()
            r.close()
            dt_str = data.get("dateTime", data.get("datetime", ""))[:19]
            date_part, time_part = dt_str.split("T")
            yr, mo, dy = [int(x) for x in date_part.split("-")]
            hr, mn, sc = [int(x) for x in time_part.split(":")]
            machine.RTC().datetime((yr, mo, dy, 0, hr, mn, sc, 0))
            print("[NTP] RTC set to " + z4(yr) + "-" + z2(mo) + "-" +
                  z2(dy) + " " + z2(hr) + ":" + z2(mn) + ":" + z2(sc) + " UTC")
            led_blink(2, 200)
            return (yr, mo, dy, hr, mn, sc)
        except Exception as e:
            print("[NTP] Failed: " + str(e))
            led_blink(5, 50)
    print("[NTP] All sources failed - using Pico RTC as-is")
    t = utime.localtime()
    return (t[0], t[1], t[2], t[3], t[4], t[5])

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = ujson.load(f)
        if "lat" in cfg and "lon" in cfg:
            return cfg
    except Exception:
        pass
    return None

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            ujson.dump(cfg, f)
        print("[Config] Saved: " + str(cfg.get("name")) +
              "  tz=" + str(cfg.get("tz_offset", MANUAL_UTC_OFFSET)))
    except Exception as e:
        print("[Config] Save error: " + str(e))

def display_separator(char="-", width=56):
    print(char * width)

def display_all(cfg):
    t = utime.localtime()
    yr, mo, dy, hr, mn, sc = t[0], t[1], t[2], t[3], t[4], t[5]
    tz_offset = cfg.get("tz_offset", MANUAL_UTC_OFFSET)
    lat  = cfg["lat"]
    lon  = cfg["lon"]
    name = cfg.get("name", str(lat) + ", " + str(lon))
    local_hr = (hr + tz_offset) % 24
    tz_str = ("UTC+" + str(tz_offset)) if tz_offset >= 0 else ("UTC" + str(tz_offset))
    display_separator("=")
    print("  WORLDWIDE-TIDE-ASTRO.INFO  -  " + name)
    display_separator("=")
    print("  UTC  : " + z4(yr) + "-" + z2(mo) + "-" + z2(dy) +
          "  " + z2(hr) + ":" + z2(mn) + ":" + z2(sc))
    print("  Local: " + z4(yr) + "-" + z2(mo) + "-" + z2(dy) +
          "  " + z2(local_hr) + ":" + z2(mn) +
          "  (" + tz_str + ")")
    display_separator()
    print("  SUN & MOON")
    display_separator("-")
    try:
        astro = get_astro_data(lat, lon, yr, mo, dy, tz_offset)
        print("  Sunrise      : " + astro["sunrise"])
        print("  Sunset       : " + astro["sunset"])
        print("  Solar Noon   : " + astro["solar_noon"])
        print("  Day Length   : " + astro["day_length"])
        display_separator(".")
        print("  Moonrise     : " + astro["moonrise"])
        print("  Moonset      : " + astro["moonset"])
        print("  Moon Phase   : " + astro["phase_name"])
        print("  Illumination : " + str(astro["illumination"]) + "%")
    except Exception as e:
        print("  [Astro error] " + str(e))
    display_separator()
    print("  TIDES")
    display_separator("-")
    try:
        tides = get_tide_data(lat, lon, tz_offset)
        if tides:
            for event in tides:
                ht_ft = str(round(event["height_ft"], 2))
                ht_m  = str(round(event["height_m"],  2))
                print("  " + event["type"] + "  " + event["time"] +
                      "  -  " + ht_ft + " ft  (" + ht_m + " m)")
        else:
            print("  No tide data returned for this location.")
    except Exception as e:
        print("  [Tide error] " + str(e))
    display_separator()
    try:
        wx = get_weather()
        if wx:
            print("  Air Temp   : " + str(wx["temp_f"]) + " F  (" + str(wx["temp_c"]) + " C)")
            print("  Humidity   : " + str(wx["humidity"]) + "%")
            print("  Pressure   : " + str(wx["pressure_inhg"]) + " inHg  (" + str(wx["pressure_hpa"]) + " hPa)")
            print("  Trend      : " + wx["trend_arrow"] + "  " + wx["trend_desc"])
            print("  Forecast   : " + wx["forecast"])
            if wx.get("water_temp_f"):
                print("  Water Temp : " + str(wx["water_temp_f"]) + " F  (" + str(wx["water_temp_c"]) + " C)")
        else:
            print("  [Weather] Sensor not available")
    except Exception as e:
        print("  [Weather error] " + str(e))
    display_separator("=")
    print("  GP15 (Pin 20) = shell refresh  |  Browser = change location")
    display_separator("=")
    print()

def timer_callback(t):
    global _log_due
    _log_due = True

def idle_hook():
    global _log_due, _cfg, _btn
    new_cfg = load_config()
    if new_cfg and new_cfg.get("name") != _cfg.get("name"):
        _cfg = new_cfg
        print("\n[Config] Location changed to: " + str(_cfg.get("name")))
    if _log_due:
        _log_due = False
        print("\n[Timer] Logging pressure...")
        log_pressure()
    if _btn.value() == 0:
        utime.sleep_ms(50)
        if _btn.value() == 0:
            utime.sleep_ms(300)
            if _cfg["lat"] != 0.0:
                print("\n[Button] Refresh triggered.")
                led_blink(1, 500)
                gc.collect()
                display_all(_cfg)
            else:
                print("\n[Button] No location set - use browser first.")

def main():
    global _log_due, _cfg, _btn
    _btn = machine.Pin(REFRESH_BTN, machine.Pin.IN, machine.Pin.PULL_UP)
    wlan = connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    if not wlan.isconnected():
        print("[FATAL] No WiFi - cannot continue.")
        return
    sync_rtc()
    _cfg = load_config()
    if _cfg:
        print("\n[Config] Loaded: " + str(_cfg.get("name")) +
              "  lat=" + str(_cfg["lat"]) +
              "  lon=" + str(_cfg["lon"]) +
              "  tz=UTC" + str(_cfg.get("tz_offset", MANUAL_UTC_OFFSET)))
    else:
        print("\n[Config] No saved location - open browser to set one.")
        _cfg = {"lat": 0.0, "lon": 0.0, "name": "Not set",
                "tz_offset": MANUAL_UTC_OFFSET}
    print("\n[Weather] Taking initial BME688 reading...")
    log_pressure()
    pressure_timer = Timer()
    pressure_timer.init(
        period=LOG_INTERVAL_MS,
        mode=Timer.PERIODIC,
        callback=timer_callback
    )
    print("[Timer] Pressure logging every 15 minutes")
    if _cfg["lat"] != 0.0:
        gc.collect()
        display_all(_cfg)
    print("\n[WebServer] Starting - open http://" + wlan.ifconfig()[0] +
          "/ to change location")
    print("[Waiting] Press GP15 (Pin 20) to GND (Pin 18) for shell refresh\n")
    led_on()
    serve_data_page(
        wlan          = wlan,
        cfg           = _cfg,
        fallback_tz   = MANUAL_UTC_OFFSET,
        save_callback = save_config,
        led_idle      = idle_hook,
        led_busy      = None
    )

main()
