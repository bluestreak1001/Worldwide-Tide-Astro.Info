import utime
import ujson

I2C_SDA      = 8
I2C_SCL      = 9
I2C_ADDR     = 0x76
I2C_ID       = 0
I2C_FREQ     = 100000
DS_PIN       = 28
PRESSURE_LOG = "pressure_log.json"
MAX_SAMPLES  = 12
TREND_RAPID  = 0.06
TREND_CHANGE = 0.02

def hpa_to_inhg(hpa):
    return hpa * 0.02953

def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0

def read_bme688():
    from machine import I2C, Pin
    import bme680
    i2c = I2C(I2C_ID, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    sensor = bme680.BME680_I2C(i2c=i2c, address=I2C_ADDR)
    utime.sleep_ms(500)
    temp_c = sensor.temperature
    humidity = sensor.humidity
    pressure_hpa = sensor.pressure
    try:
        gas = sensor.gas
    except:
        gas = None
    return {
        "temp_c": round(temp_c, 1),
        "temp_f": round(c_to_f(temp_c), 1),
        "humidity": round(humidity, 1),
        "pressure_hpa": round(pressure_hpa, 2),
        "pressure_inhg": round(hpa_to_inhg(pressure_hpa), 3),
        "gas": gas,
    }

def read_ds18b20():
    import onewire, ds18x20
    from machine import Pin
    ds = ds18x20.DS18X20(onewire.OneWire(Pin(DS_PIN)))
    roms = ds.scan()
    if not roms:
        return None, None
    ds.convert_temp()
    utime.sleep_ms(750)
    temp_c = ds.read_temp(roms[0])
    return round(temp_c, 1), round(c_to_f(temp_c), 1)

def load_log():
    try:
        with open(PRESSURE_LOG, "r") as f:
            data = ujson.load(f)
        if isinstance(data, list):
            return data
    except:
        pass
    return []

def save_log(log):
    try:
        with open(PRESSURE_LOG, "w") as f:
            ujson.dump(log, f)
    except Exception as e:
        print("[Weather] Log error: " + str(e))

def append_reading(pressure_inhg, timestamp_sec):
    log = load_log()
    log.append({"p": round(pressure_inhg, 3), "t": timestamp_sec})
    if len(log) > MAX_SAMPLES:
        log = log[-MAX_SAMPLES:]
    save_log(log)
    return log

def get_trend(log):
    if not log or len(log) < 2:
        return ("?", "Insufficient data", 0.0)
    change = log[-1]["p"] - log[0]["p"]
    ac = abs(change)
    if ac >= TREND_RAPID:
        return ("^^","Rising Rapidly",change) if change>0 else ("vv","Falling Rapidly",change)
    elif ac >= TREND_CHANGE:
        return ("^","Rising",change) if change>0 else ("v","Falling",change)
    return ("-","Steady",change)

def get_forecast(arrow):
    f = {"^^":"Fair weather likely - watch for wind shift",
         "^":"Improving conditions expected",
         "-":"Settled weather - conditions stable",
         "v":"Deteriorating - possible rain or wind",
         "vv":"Storm warning - significant weather approaching",
         "?":"Building pressure history..."}
    return f.get(arrow,"")

def log_pressure():
    try:
        bme = read_bme688()
        now = utime.time()
        append_reading(bme["pressure_inhg"], now)
        print("[Weather] Logged " + str(bme["pressure_inhg"]) + " inHg  " +
              str(bme["temp_f"]) + "F  " + str(bme["humidity"]) + "%RH")
    except Exception as e:
        print("[Weather] Log error: " + str(e))

def get_weather():
    try:
        bme = read_bme688()
        now = utime.time()
        log = append_reading(bme["pressure_inhg"], now)
        arrow, desc, change = get_trend(log)
        water_c, water_f = read_ds18b20()
        return {
            "temp_c": bme["temp_c"],
            "temp_f": bme["temp_f"],
            "humidity": bme["humidity"],
            "pressure_hpa": bme["pressure_hpa"],
            "pressure_inhg": bme["pressure_inhg"],
            "gas": bme["gas"],
            "trend_arrow": arrow,
            "trend_desc": desc,
            "trend_change": change,
            "forecast": get_forecast(arrow),
            "water_temp_c": water_c,
            "water_temp_f": water_f,
            "log": log,
        }
    except Exception as e:
        print("[Weather] Read error: " + str(e))
        return None
