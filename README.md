# Worldwide-Tide-Astro.Info

A self-contained marine and astronomical station running on a **Raspberry Pi Pico W**.
Displays real-time tides, current weather conditions, a 2-day forecast, and full
sun/moon data — all served over your local WiFi network as a mobile-friendly web page.

Works for any coastal location worldwide.

---

## Features

- 🌊 **Tides** — High/low tide times and heights via WorldTides API (Chart Datum)
- 🌡 **Current Conditions** — Temperature, humidity, pressure, wind, precipitation via Open-Meteo
- 📅 **2-Day Forecast** — High/low temps, conditions, wind, precipitation probability
- ☀️ **Sun Data** — Sunrise, sunset, solar noon, day length via sunrise-sunset.org
- 🌕 **Moon Data** — Moonrise/moonset (Meeus algorithm, no API needed), phase name, illumination
- 📡 **Local Sensors** — BME688 for air temp/humidity/pressure with trend logging; DS18B20 for water temp
- 🌍 **Location Search** — Geocode any location by name; save favorites; auto timezone detection
- 🔘 **Hardware Button** — GP15 triggers a full shell readout without touching a browser

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
|---------|---------|-------------|
| WorldTides | Tide predictions | Yes (free tier available) |
| Open-Meteo | Weather and forecast | No |
|
