"""
reports.py - fetch the distilled Long Island fishing-report feed on the Pico.

The heavy HTML scraping is done OFF the device by tools/li_report_scraper.py,
which publishes a small (~5 KB) li_report.json keyed by waters class. This
module just fetches that JSON and returns the slice for the station's own
waters. Point REPORT_FEED_URL (in secrets.py) at wherever you host the file -
a GitHub raw URL, a gist, or a small web server on the same Pi that scrapes.

Everything degrades gracefully: if the URL is unset or unreachable, the rest of
the station is unaffected and get_report() simply returns None.
"""


def feed_url(url=None):
    if url:
        return url
    try:
        import secrets
        return getattr(secrets, "REPORT_FEED_URL", "") or ""
    except Exception:
        return ""


def get_report(waters=None, url=None):
    """
    Return the report slice for `waters`, or None if unavailable.
    Shape: {updated, source, waters, label, species[], reports[], summary,
            other_areas[]}.
    """
    u = feed_url(url)
    if not u:
        return None
    try:
        import urequests
        r = urequests.get(u, timeout=12)
        data = r.json()
        r.close()
    except Exception as e:
        print("[Reports] fetch error: " + str(e))
        return None

    areas = data.get("areas", {}) if isinstance(data, dict) else {}
    if not areas:
        return None

    area = None
    if waters and waters in areas:
        area = areas[waters]
    if area is None:
        area = areas.get("unclassified")
    if area is None:
        # first available classified area
        for k in areas:
            area = areas[k]
            break

    other = [k for k in areas if area is None or areas[k] is not area]
    return {
        "updated":     data.get("updated"),
        "source":      data.get("source"),
        "source_url":  data.get("source_url"),
        "waters":      waters,
        "label":       area.get("label", "") if area else "",
        "species":     area.get("species", []) if area else [],
        "reports":     area.get("reports", []) if area else [],
        "summary":     area.get("summary", "") if area else "",
        "other_areas": other,
    }
