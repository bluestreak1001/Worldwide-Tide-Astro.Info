import socket
import urequests
import ujson
import utime

FAVORITES_FILE = "favorites.json"

def url_decode(s):
    s = s.replace("+", " ")
    result = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i+2 < len(s):
            try:
                result.append(chr(int(s[i+1:i+3], 16)))
                i += 3
                continue
            except:
                pass
        result.append(s[i])
        i += 1
    return "".join(result)

def parse_query(qs):
    params = {}
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[url_decode(k)] = url_decode(v)
    return params

def load_favorites():
    try:
        with open(FAVORITES_FILE, "r") as f:
            data = ujson.load(f)
        if isinstance(data, list):
            return data
    except:
        pass
    return []

def save_favorite(name, lat, lon, tz):
    favs = load_favorites()
    favs = [f for f in favs if f.get("name","").lower() != name.lower()]
    favs.insert(0, {"name":name,"lat":lat,"lon":lon,"tz_offset":tz})
    favs = favs[:8]
    try:
        with open(FAVORITES_FILE, "w") as f:
            ujson.dump(favs, f)
    except Exception as e:
        print("[Fav] " + str(e))

def geocode_query(query):
    enc = query.strip().replace(" ", "+")
    url = "https://nominatim.openstreetmap.org/search?q=" + enc + "&format=json&limit=1"
    headers = {"User-Agent": "PicoW-AstroStation/1.0"}
    print("[Geocode] " + url)
    r = urequests.get(url, headers=headers, timeout=12)
    raw = r.text
    r.close()
    results = ujson.loads(raw)
    if not results:
        raise ValueError("Not found: " + query)
    top = results[0]
    return float(top["lat"]), float(top["lon"]), str(top.get("display_name", query))

def get_timezone_offset(lat, lon, fallback):
    try:
        url = ("https://timeapi.io/api/timezone/coordinate?latitude=" +
               str(lat) + "&longitude=" + str(lon))
        r = urequests.get(url, timeout=10)
        data = r.json()
        r.close()
        sec = data.get("currentUtcOffset", {}).get("seconds", None)
        if sec is not None:
            return int(sec) // 3600
    except Exception as e:
        print("[TZ] " + str(e))
    return fallback

def send_response(conn, status, body):
    b = body.encode("utf-8")
    h = ("HTTP/1.1 " + status + "\r\nContent-Type: text/html; charset=utf-8\r\n" +
         "Content-Length: " + str(len(b)) + "\r\nConnection: close\r\n\r\n")
    conn.sendall(h.encode("utf-8") + b)

def send_redirect(conn, loc):
    conn.sendall(("HTTP/1.1 302 Found\r\nLocation: " + loc + "\r\nConnection: close\r\n\r\n").encode())

def _fetch_data(lat, lon, name, tz):
    from astro import get_astro_data
    from tides import get_tide_data
    from weather import get_weather
    t = utime.localtime()
    yr,mo,dy,hr,mn,sc = t[0],t[1],t[2],t[3],t[4],t[5]
    def z2(n):
        s=str(int(n)); return s if len(s)>=2 else "0"+s
    def z4(n):
        s=str(int(n))
        while len(s)<4: s="0"+s
        return s
    lh = (hr+tz)%24
    tzs = ("UTC+"+str(tz)) if tz>=0 else ("UTC"+str(tz))
    r = {"name":name,
         "utc":z4(yr)+"-"+z2(mo)+"-"+z2(dy)+" "+z2(hr)+":"+z2(mn)+":"+z2(sc),
         "local":z4(yr)+"-"+z2(mo)+"-"+z2(dy)+" "+z2(lh)+":"+z2(mn),
         "tz_str":tzs,
         "astro":None,"astro_err":None,
         "tides":None,"tide_err":None,
         "weather":None,"wx_err":None}
    try: r["astro"] = get_astro_data(lat,lon,yr,mo,dy,tz)
    except Exception as e: r["astro_err"] = str(e)
    try: r["tides"] = get_tide_data(lat,lon,tz)
    except Exception as e: r["tide_err"] = str(e)
    try: r["weather"] = get_weather()
    except Exception as e: r["wx_err"] = str(e)
    try:
        from astro import get_forecast
        r["forecast"] = get_forecast(lat,lon)
    except Exception as e:
        r["forecast"] = None

    # --- Boating/Fishing conditions + local waters report ------------------
    r["waters"] = None; r["conditions"] = None; r["cond_err"] = None
    r["current"] = None; r["marine"] = None; r["solunar"] = None
    r["report"] = None
    try:
        import conditions as _cond
        import solunar as _sol
        from astro import get_current, get_marine
        waters = _cond.guess_waters(name, lat, lon)
        r["waters"] = waters
        try: r["current"] = get_current(lat, lon)
        except Exception as e: print("[Cond] current: "+str(e))
        try: r["marine"] = get_marine(lat, lon)
        except Exception as e: print("[Cond] marine: "+str(e))
        cur = r["current"] or {}
        mar = r["marine"] or {}
        a = r.get("astro") or {}
        sol = _sol.solunar_now(a.get("moonrise"), a.get("moonset"),
                               a.get("illumination"), lh, mn)
        r["solunar"] = sol
        try: tide_mv = _cond.tide_movement(r.get("tides") or [], utime.time())
        except Exception: tide_mv = None
        wx = r.get("weather") or {}
        wave_ft = None
        if mar.get("wave_height_m") is not None:
            wave_ft = round(mar["wave_height_m"] * 3.28084, 1)
        inp = {
            "waters": waters,
            "wind_mph": cur.get("wind_mph"), "gust_mph": cur.get("gust_mph"),
            "wind_dir": cur.get("wind_dir"), "wave_ft": wave_ft,
            "swell_period_s": mar.get("wave_period"),
            "weather_code": cur.get("weather_code"),
            "precip_in": cur.get("precip_in"),
            "pressure_arrow": wx.get("trend_arrow"),
            "water_temp_f": mar.get("water_temp_f"),
            "solunar": sol, "tide": tide_mv,
            "tide_moving": (tide_mv.get("moving") if tide_mv else 0),
            "month": mo,
        }
        r["conditions"] = _cond.assess(inp)
    except Exception as e:
        r["cond_err"] = str(e)
    try:
        import reports as _rep
        r["report"] = _rep.get_report(r.get("waters"))
    except Exception as e:
        print("[Report] "+str(e))
    return r

def _row(label, val, color=""):
    cs = " style=\"color:"+color+"\"" if color else ""
    return ("<tr><td style=\"color:#6a8aaa;padding:7px 0;border-bottom:1px solid #0f1e30\">"+label+
            "</td><td"+cs+" style=\"text-align:right;padding:7px 0;border-bottom:1px solid #0f1e30\">"+str(val)+"</td></tr>")

def _score_color(score):
    if score >= 7: return "#80d8a0"
    if score >= 5: return "#f0c040"
    if score >= 3: return "#f0a040"
    return "#f07070"

def _build_page(data, lat, lon, query, tz):
    name = data.get("name", query)
    a    = data.get("astro") or {}
    ae   = data.get("astro_err","")
    tides= data.get("tides") or []
    te   = data.get("tide_err","")
    wx   = data.get("weather") or {}
    we   = data.get("wx_err","")
    tzs  = data.get("tz_str","")

    # --- Boating & Fishing scores ---
    cond = data.get("conditions")
    cond_html = ""
    if data.get("cond_err"):
        cond_html = "<tr><td colspan=2 style=\"color:#f07070\">"+data["cond_err"]+"</td></tr>"
    elif cond:
        b = cond["boating"]; f = cond["fishing"]
        cond_html += _row("Waters", cond.get("waters_label",""))
        cond_html += _row("Boating Day", str(b["score"])+" / 10 &nbsp; "+b["label"], _score_color(b["score"]))
        if b.get("detail"):
            cond_html += _row("", b["detail"])
        for fl in b.get("flags",[]):
            cond_html += _row("", "&#9888; "+fl, "#f0a040")
        cond_html += _row("Fishing Day", str(f["score"])+" / 10 &nbsp; "+f["label"], _score_color(f["score"]))
        if f.get("window"):
            cond_html += _row("Best Window", f["window"], "#80d8a0")
        for nt in f.get("notes",[]):
            cond_html += _row("", nt, "#6a8aaa")
        cond_html += ("<tr><td colspan=2 style=\"color:#4a9eff;padding:10px 0 4px;font-weight:bold\">"
                      +cond.get("verdict","")+"</td></tr>")
    else:
        cond_html = "<tr><td colspan=2 style=\"color:#6a8aaa\">Conditions unavailable</td></tr>"

    # --- Local waters fishing report ---
    rep = data.get("report")
    report_html = ""
    if not rep or not rep.get("reports"):
        report_html = ("<tr><td colspan=2 style=\"color:#6a8aaa\">No local report. "
                       "Run tools/li_report_scraper.py and set REPORT_FEED_URL in secrets.py.</td></tr>")
    else:
        if rep.get("label"):
            report_html += _row("Area", rep["label"])
        if rep.get("species"):
            sp = ", ".join(rep["species"][:6])
            report_html += _row("Biting", sp[:1].upper()+sp[1:], "#80d8a0")
        for rr in rep["reports"][:3]:
            where = rr.get("where") or rep.get("label","")
            report_html += ("<tr><td colspan=2 style=\"padding:7px 0;border-bottom:1px solid #0f1e30\">"
                "<span style=\"color:#4a9eff;font-weight:bold\">"+where+"</span> "
                "<span style=\"color:#c8daf0\">"+rr.get("text","")+"</span></td></tr>")
        upd = (rep.get("updated") or "")[:10]
        src = rep.get("source","") or ""
        report_html += ("<tr><td colspan=2 style=\"color:#2a4a6a;font-size:0.68rem;padding-top:8px\">"
                        +src+(" &mdash; "+upd if upd else "")+"</td></tr>")

    tide_html = ""
    if te:
        tide_html = "<tr><td colspan=2 style=\"color:#f07070\">"+te+"</td></tr>"
    elif not tides:
        tide_html = "<tr><td colspan=2 style=\"color:#f07070\">No tide data</td></tr>"
    else:
        for ev in tides:
            is_high = "H" in ev["type"].upper()
            lbl = "HIGH TIDE" if is_high else "LOW TIDE"
            col = "#ffb347" if is_high else "#00d4aa"
            ht_ft = str(round(ev["height_ft"],2))
            ht_m  = str(round(ev["height_m"],2))
            tide_html += ("<tr>"
                "<td style=\"color:"+col+";padding:9px 0;border-bottom:1px solid #0f1e30;font-weight:bold\">"+lbl+"</td>"
                "<td style=\"text-align:right;padding:9px 0;border-bottom:1px solid #0f1e30;color:#fff\">"+ev["time"]+" &mdash; "+ht_ft+" ft ("+ht_m+" m)</td>"
                "</tr>")

    wx_html = ""
    if we:
        wx_html = "<tr><td colspan=2 style=\"color:#f07070\">"+we+"</td></tr>"
    elif wx:
        wx_html += _row("Air Temp", str(wx.get("temp_f","--"))+" F  ("+str(wx.get("temp_c","--"))+" C)")
        wx_html += _row("Humidity", str(wx.get("humidity","--"))+"%")
        wx_html += _row("Pressure", str(wx.get("pressure_inhg","--"))+" inHg  ("+str(wx.get("pressure_hpa","--"))+" hPa)")
        wx_html += _row("Trend", wx.get("trend_arrow","-")+"  "+wx.get("trend_desc",""))
        wx_html += _row("Forecast", wx.get("forecast",""))
        wt = wx.get("water_temp_f")
        if wt is not None:
            if -20 < float(wt) < 120:
                wx_html += _row("Water Temp", str(wt)+" F  ("+str(wx.get("water_temp_c","--"))+" C)", "#80d8a0")
            else:
                wx_html += _row("Water Temp", "Sensor Error", "#f07070")
    else:
        wx_html = "<tr><td colspan=2 style=\"color:#f07070\">Weather unavailable</td></tr>"

    fc_html = ""
    fc = data.get("forecast") or []
    if not fc:
        fc_html = "<tr><td colspan=2 style=\"color:#f07070\">Forecast unavailable</td></tr>"
    else:
        labels = ["Today", "Tomorrow"]
        for i,day in enumerate(fc):
            lbl = labels[i] if i < len(labels) else day.get("date","")
            fc_html += ("<tr><td colspan=2 style=\"color:#4a9eff;padding:6px 0 2px 0;font-weight:bold;border-bottom:1px solid #1a3050\">"+lbl+" &mdash; "+day.get("date","")+"</td></tr>")
            fc_html += _row("High / Low", day.get("high","--")+" F / "+day.get("low","--")+" F")
            fc_html += _row("Conditions", day.get("conditions","--"))
            fc_html += _row("Precip Chance", day.get("precip","--")+"%")
            fc_html += _row("Wind", day.get("wind_dir","--")+" "+day.get("wind","--")+" mph")

    sun_html = ""
    if ae:
        sun_html = "<tr><td colspan=2 style=\"color:#f07070\">"+ae+"</td></tr>"
    else:
        for lbl,key,suf in [("Sunrise","sunrise",""),("Sunset","sunset",""),
                            ("Solar Noon","solar_noon",""),("Day Length","day_length",""),
                            ("Moonrise","moonrise",""),("Moonset","moonset",""),
                            ("Moon Phase","phase_name",""),("Illumination","illumination","%")]:
            sun_html += _row(lbl, str(a.get(key,"--"))+suf)

    nm_js = name.replace("\\","\\\\").replace("'","\\'")
    return ("<!DOCTYPE html><html><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>"+name+"</title>"
        "<style>"
        "body{background:#060d18;color:#c8daf0;font-family:monospace;padding:16px;max-width:520px;margin:0 auto;}"
        "h1{color:#4a9eff;font-size:1.3rem;margin-bottom:4px;text-align:center;}"
        ".sub{color:#2a4a6a;font-size:0.72rem;margin-bottom:16px;text-align:center;}"
        "h2{color:#4a9eff;font-size:0.68rem;letter-spacing:0.15em;text-transform:uppercase;"
        "margin:20px 0 8px;padding-bottom:4px;border-bottom:1px solid #1a3050;}"
        "table{width:100%;border-collapse:collapse;margin-bottom:4px;}"
        "td{font-size:0.85rem;}"
        ".btn{display:inline-block;padding:10px 18px;border-radius:8px;font-family:monospace;"
        "font-size:0.82rem;cursor:pointer;border:none;margin:3px;}"
        ".save{background:#1a5a30;color:#80d8a0;}"
        ".again{background:#1a2a40;color:#c8daf0;border:1px solid #1a3050;}"
        ".btnrow{margin-bottom:16px;}"
        ".footer{color:#2a4a6a;font-size:0.65rem;text-align:center;margin-top:24px;"
        "padding-top:12px;border-top:1px solid #0f1e30;}"
        "</style></head><body>"
        "<h1>&#127758; "+name+"</h1>"
        "<p class=\"sub\">"+tzs+" &nbsp;|&nbsp; "+data.get("utc","")+" &nbsp;|&nbsp; Local: "+data.get("local","")+"</p>"
        "<div class=\"btnrow\">"
        "<button class=\"btn save\" onclick=\"saveNow()\">&#10003; Save Location</button>"
        "<button class=\"btn again\" onclick=\"searchAgain()\">&#8634; Search Another</button>"
        "</div>"
        "<h2>&#9973; Boating &amp; Fishing Day</h2><table>"+cond_html+"</table>"
        "<h2>&#127907; Local Fishing Report</h2><table>"+report_html+"</table>"
        "<h2>&#127754; Tides</h2><table>"+tide_html+"</table>"
        "<h2>&#127777; Weather</h2><table>"+wx_html+"</table>"
        "<h2>&#128197; Forecast</h2><table>"+fc_html+"</table>"
        "<h2>&#9728; Sun &amp; Moon</h2><table>"+sun_html+"</table>"
        "<p class=\"footer\">Worldwide-Tide-Astro.Info &mdash; local network only</p>"
        "<script>"
        "function saveNow(){window.location.href='/save?lat="+str(lat)+"&lon="+str(lon)+"&tz="+str(tz)+"&name='+encodeURIComponent('"+nm_js+"');}"
        "function searchAgain(){window.location.href='/';}"
        "</script></body></html>")

_cache = {}

def serve_data_page(wlan, cfg, fallback_tz, save_callback,
                    led_idle=None, led_busy=None, port=80):
    ip = wlan.ifconfig()[0]
    print("[WebServer] Running at http://" + ip + "/")
    addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(3)
    s.settimeout(1)
    saved_name = cfg.get("name","") if cfg else ""
    try:
        while True:
            if led_idle: led_idle()
            conn = None
            try: conn, client = s.accept()
            except OSError: continue
            try:
                raw = conn.recv(2048).decode("utf-8","ignore")
                if not raw: conn.close(); conn=None; continue
                parts = raw.split("\r\n")[0].split(" ")
                path = parts[1] if len(parts)>1 else "/"
                if path=="/" or path=="":
                    favs = load_favorites()
                    qpicks = ["Fire Island Inlet, NY","Shinnecock Inlet, NY",
                              "Montauk Point, NY","Northport Harbor, NY",
                              "Port Jefferson, NY","Babylon, NY",
                              "Chestertown, MD","Sandy Hook, NJ"]
                    qp = "".join(['<button onclick="s(this.innerText)" style="background:#0d1e35;border:1px solid #1a3050;border-radius:6px;color:#a8c8f0;padding:8px 10px;margin:3px;cursor:pointer;font-family:monospace;font-size:0.78rem;">'+q+"</button>" for q in qpicks])
                    fp = "".join(['<button onclick="s(this.innerText)" style="background:#0a2018;border:1px solid #1a4a30;border-radius:6px;color:#80d8a0;padding:8px 10px;margin:3px;cursor:pointer;font-family:monospace;font-size:0.78rem;">'+f["name"]+"</button>" for f in favs])
                    cur = ('<p style="color:#6a8aaa;font-size:0.75rem;margin-bottom:12px;">Current: <span style="color:#00d4aa">'+saved_name+"</span></p>") if saved_name else ""
                    html = ("<!DOCTYPE html><html><head><meta charset=\"UTF-8\">"
                        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                        "<title>Worldwide-Tide-Astro.Info</title>"
                        "<style>"
                        "body{background:#060d18;color:#c8daf0;font-family:monospace;padding:20px;max-width:520px;margin:0 auto;}"
                        "h1{color:#4a9eff;font-size:1.4rem;text-align:center;margin-bottom:4px;}"
                        ".sub{color:#2a4a6a;font-size:0.72rem;text-align:center;margin-bottom:20px;}"
                        "input{width:100%;padding:12px;background:#0d1e35;border:1px solid #1a3050;border-radius:8px;"
                        "color:#fff;font-family:monospace;font-size:0.95rem;margin-bottom:8px;box-sizing:border-box;}"
                        ".go{width:100%;padding:12px;background:#4a9eff;border:none;border-radius:8px;"
                        "color:#000;font-family:monospace;font-weight:bold;font-size:0.95rem;cursor:pointer;margin-bottom:20px;}"
                        ".sec{font-size:0.65rem;color:#2a4a6a;letter-spacing:0.15em;text-transform:uppercase;margin:12px 0 8px;}"
                        ".footer{color:#2a4a6a;font-size:0.65rem;text-align:center;margin-top:24px;}"
                        "</style></head><body>"
                        "<h1>&#127758; Worldwide-Tide-Astro.Info</h1>"
                        "<p class=\"sub\">Tides &bull; Weather &bull; Astronomy</p>"
                        +cur+
                        "<input type=\"text\" id=\"loc\" placeholder=\"e.g. Fire Island Inlet, NY\">"
                        "<button class=\"go\" onclick=\"doSearch()\">GO</button>"
                        "<p class=\"sec\">Quick Picks</p>"+qp+
                        (("<p class=\"sec\">Recently Used</p>"+fp) if favs else "")+
                        "<p class=\"footer\">Worldwide-Tide-Astro.Info &mdash; local network only</p>"
                        "<script>"
                        "function s(v){document.getElementById('loc').value=v;doSearch();}"
                        "function doSearch(){var q=document.getElementById('loc').value.trim();"
                        "if(!q)return;window.location.href='/search?q='+encodeURIComponent(q);}"
                        "document.getElementById('loc').addEventListener('keydown',function(e){if(e.key==='Enter')doSearch();});"
                        "</script></body></html>")
                    send_response(conn, "200 OK", html)
                elif path.startswith("/search"):
                    qs = path.split("?",1)[1] if "?" in path else ""
                    q = parse_query(qs).get("q","").strip()
                    if not q: send_redirect(conn, "/")
                    else:
                        loading = ("<!DOCTYPE html><html><head><meta charset=\"UTF-8\">"
                            "<meta http-equiv=\"refresh\" content=\"3;url=/result?q="+q.replace(" ","+")+"\"><style>"
                            "body{background:#060d18;color:#c8daf0;font-family:monospace;"
                            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}"
                            ".box{text-align:center;padding:20px;}</style></head><body>"
                            "<div class=\"box\"><p style=\"font-size:2rem;margin-bottom:12px\">&#9203;</p>"
                            "<p style=\"color:#4a9eff;font-size:1rem\">Looking up "+q+"...</p>"
                            "<p style=\"color:#2a4a6a;font-size:0.75rem;margin-top:8px\">Fetching tides, weather &amp; astro data</p>"
                            "</div></body></html>")
                        send_response(conn, "200 OK", loading)
                        conn.close(); conn=None
                        try:
                            lat2,lon2,disp = geocode_query(q)
                            tz2 = get_timezone_offset(lat2, lon2, fallback_tz)
                            _cache[q] = (lat2,lon2,disp,tz2)
                        except Exception as e:
                            print("[Search] "+str(e)); _cache[q]=None
                elif path.startswith("/result"):
                    qs = path.split("?",1)[1] if "?" in path else ""
                    q = parse_query(qs).get("q","").strip()
                    cached = _cache.get(q)
                    if not cached: send_redirect(conn, "/")
                    else:
                        lat2,lon2,disp,tz2 = cached
                        d = _fetch_data(lat2,lon2,q,tz2)
                        send_response(conn,"200 OK",_build_page(d,lat2,lon2,q,tz2))
                elif path.startswith("/save"):
                    qs = path.split("?",1)[1] if "?" in path else ""
                    p = parse_query(qs)
                    try:
                        lat2=float(p.get("lat","0")); lon2=float(p.get("lon","0"))
                        tz2=int(p.get("tz",str(fallback_tz))); nm=p.get("name","Unknown")
                        save_callback({"name":nm,"lat":lat2,"lon":lon2,"tz_offset":tz2})
                        save_favorite(nm,lat2,lon2,tz2)
                        saved_name=nm
                        ok = ("<!DOCTYPE html><html><head><meta charset=\"UTF-8\"><style>"
                            "body{background:#060d18;color:#c8daf0;font-family:monospace;"
                            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}"
                            ".box{text-align:center;max-width:400px;padding:20px;}</style></head><body>"
                            "<div class=\"box\"><p style=\"font-size:2rem;margin-bottom:8px\">&#10003;</p>"
                            "<p style=\"color:#80d8a0;font-size:1.1rem;margin-bottom:8px\">"+nm+"</p>"
                            "<p style=\"color:#2a4a6a;font-size:0.75rem\">Location saved.</p>"
                            "<a href=\"/\" style=\"display:inline-block;margin-top:16px;padding:10px 24px;"
                            "background:#1a2a40;border-radius:8px;color:#c8daf0;text-decoration:none;"
                            "font-family:monospace;border:1px solid #1a3050;\">&#8592; Search Another</a>"
                            "</div></body></html>")
                        send_response(conn,"200 OK",ok)
                        print("[Save] "+nm)
                    except Exception as e:
                        print("[Save] "+str(e)); send_redirect(conn,"/")
                else:
                    send_response(conn,"404 Not Found","<h1 style='color:#fff'>404</h1>")
            except Exception as e:
                print("[WebServer] "+str(e))
            finally:
                if conn:
                    try: conn.close()
                    except: pass
    finally:
        try: s.close()
        except: pass
