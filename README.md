# Worldwide-Tide-Astro.Info

A self-contained marine and astronomical station running on a **Raspberry Pi Pico W**.
Displays real-time tides, current weather conditions, a 2-day forecast, and full
sun/moon data — all served over your local WiFi network as a mobile-friendly web page.

It also scores each day for **boating** and **fishing**, tuned to the specific
Long Island waters the station sits on, and can surface a distilled local
fishing report for those waters.

Works for any coastal location worldwide; the boating/fishing scoring works
everywhere, and the Long Island report + waters-tuning kicks in for LI harbors.

---

## Features

- 🌊 **Tides** — High/low tide times and heights via WorldTides API (Chart Datum)
- ⛵ **Boating Day score (0–10)** — Is it safe/comfortable to be on *this* water today? Combines wind/gusts (Open-Meteo) and sea state (Open-Meteo Marine), with thresholds that adapt to the waters class — a stiff breeze that shuts down the open ocean is a fine day inside a protected bay, and inlets flag wind-over-tide chop.
- 🎣 **Fishing Day score (0–10)** — Are fish likely feeding? Combines **solunar** major/minor feeding periods (computed on-device from the moon), barometric trend (BME688 when installed), tide movement, wind, and water temperature.
- 🐟 **Local Fishing Report** — A distilled, waters-specific Long Island report (species + shop/charter snippets), fetched as a small JSON feed. Heavy scraping runs off-device (see [Architecture](#architecture-why-a-companion-scraper)).
- 🌡 **Current Conditions** — Temperature, humidity, pressure, wind, precipitation via Open-Meteo
- 📅 **2-Day Forecast** — High/low temps, conditions, wind, precipitation probability
- ☀️ **Sun Data** — Sunrise, sunset, solar noon, day length via sunrise-sunset.org
- 🌕 **Moon Data** — Moonrise/moonset (Meeus algorithm, no API needed), phase name, illumination
- 📡 **Local Sensors** — BME688 for air temp/humidity/pressure with trend logging; DS18B20 for water temp
- 🌍 **Location Search** — Geocode any location by name; save favorites; auto timezone detection
- 🔘 **Hardware Button** — GP15 triggers a full shell readout without touching a browser

### Waters classes (Long Island)

The station classifies its harbor into a waters class (from the location name,
with a lat/lon fallback) and tunes the scores and picks the matching report:

| Class | Examples | Character |
|-------|----------|-----------|
| `north-shore` | Port Jefferson, Northport, Huntington | LI Sound / North Shore — protected-ish, tide-driven |
| `south-shore-bays` | Great South Bay, Moriches, Jamaica Bay | Shallow protected bays |
| `inlets` | Fire Island, Jones, Moriches, Shinnecock | Current + wind-against-tide danger |
| `ocean` | South-shore ocean, offshore reefs, Montauk | Exposed, swell-driven |
| `peconics` | Peconic Bay, Gardiners Bay, Orient | The Forks, mixed |

---

## Hardware

| Component | Purpose |
|-----------|---------|
| Raspberry Pi Pico W | Main controller |
| BME688 (I2C, 0x76) | Air temp, humidity, pressure, gas |
| DS18B20 (OneWire, GP28) | Water temperature |
| Momentary button (GP15 → GND) | Shell display refresh |

**Wiring:**
- BME688: SDA → GP8, SCL → GP9, VCC → 3.3V
- DS18B20: Data → GP28, VCC → 3.3V, GND → GND (4.7kΩ pull-up on data line)
- Button: GP15 → GND (Pin 18)

---

## Setup

### 1. Install MicroPython
Flash the latest MicroPython firmware onto your Pico W from [micropython.org](https://micropython.org/download/rp2-pico-w/).

### 2. Install the BME680 library
Copy bme680.py to /lib on the Pico W.
Available from: https://github.com/pimoroni/bme680-python

### 3. Configure credentials
Copy secrets_template.py to secrets.py and fill in your real values.
Get a free WorldTides API key at https://www.worldtides.info

### 4. Set your timezone offset
In main.py, set MANUAL_UTC_OFFSET to your UTC offset:
-4 for EDT (summer), -5 for EST (winter)

### 5. Deploy to Pico W
Copy all .py files to the root of the Pico W using Thonny or mpremote.

---

## APIs Used

| Service | Purpose | Key Required |
|---------|---------|--------------|
| WorldTides | Tide predictions | Yes (free tier available) |
| Open-Meteo | Weather + 2-day forecast + current wind/gust | No |
| Open-Meteo Marine | Wave height/period, sea-surface temp | No |
| sunrise-sunset.org | Sun times | No |
| Nominatim (OpenStreetMap) | Geocoding location search | No |
| timeapi.io | Timezone offset by coordinate | No |

All feeds are keyless except WorldTides. Solunar feeding periods and the
moon ephemeris are computed **on-device** — no service required.

---

## Architecture (why a companion scraper)

The Pico W has ~264 KB RAM, a minimal `re` module, and memory-limited HTTPS —
it cannot reliably fetch and parse the 250–500 KB, JavaScript-heavy fishing-
report web pages. So the work is split:

```
  ┌─────────────────────────────┐        ┌──────────────────────────────┐
  │  Companion host (Pi / PC)   │        │        Raspberry Pi Pico W    │
  │  tools/li_report_scraper.py │        │                               │
  │   • scrape LI report pages  │        │   reports.py                  │
  │   • tag snippets to waters  │  HTTP  │    • fetch li_report.json     │
  │   • distill to ~5 KB JSON   │──────► │    • pick this waters' slice  │
  │   • publish li_report.json  │  GET   │   conditions.py + solunar.py  │
  └─────────────────────────────┘        │    • score boating + fishing  │
                                         └──────────────────────────────┘
```

The **boating/fishing scores are always computed on-device** from keyless
structured data — the report feed is an optional narrative layer on top.

### On-device modules

| File | Role |
|------|------|
| `conditions.py` | Boating + Fishing scoring engine; waters classification (pure, unit-testable) |
| `solunar.py` | Solunar major/minor feeding periods + score from moon rise/set/illumination (pure) |
| `reports.py` | Fetches the distilled report feed and returns the slice for the station's waters |
| `astro.py` | Sun/moon/marine/current-weather fetches |

---

## Long Island fishing-report feed (optional)

The narrative report is optional. Without it, the station still shows boating
and fishing scores; with it, you also get species + local snippets for your
waters.

### 1. Run the scraper on a full computer (e.g. the Pi that hosts this repo)

```bash
python3 tools/li_report_scraper.py           # writes data/li_report.json
python3 tools/li_report_scraper.py --print   # or print to stdout
```

Standard-library only — no `pip install`. It finds the latest On The Water
"Long Island and NYC Fishing Report", parses each shop/charter block, tags it
to a waters class, and distills everything to a ~5 KB JSON. The schema is
documented by `data/li_report.sample.json`. The live `data/li_report.json` is
**gitignored** (it contains third-party content — host it, don't redistribute).

### 2. Host `li_report.json` somewhere the Pico can reach

A small web server on the same Pi, a private gist, or any static host works.
Refresh it on a schedule (the reports update roughly weekly), e.g. a cron job:

```cron
# Re-scrape every day at 6am
0 6 * * *  cd /path/to/Worldwide-Tide-Astro.Info && python3 tools/li_report_scraper.py
```

### 3. Point the Pico at it

In `secrets.py`:

```python
REPORT_FEED_URL = "http://192.168.1.x:8000/li_report.json"   # or your host
```

Leave it `""` to disable the report layer entirely.
