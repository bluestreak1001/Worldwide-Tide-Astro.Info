#!/usr/bin/env python3
"""
li_report_scraper.py - Companion scraper for Worldwide-Tide-Astro.Info

Runs on a full computer (e.g. the Raspberry Pi that hosts this repo), NOT on the
Pico W. The Pico has ~264 KB RAM and no HTML parser, so scraping 250-500 KB
fishing-report pages there is not viable. This script does the heavy parsing and
distills everything into a tiny `li_report.json` (a few KB) that the Pico fetches
over HTTP via reports.py.

Source: On The Water "Long Island and NYC Fishing Report" (published ~weekly).
The report is organized as shop -> location blocks, which we tag to a Long Island
"waters class" so the device can show the report for its own waters:

    north-shore     LI Sound / North Shore harbors
    south-shore-bays  Great South Bay, Moriches, Jamaica Bay, etc.
    inlets          Fire Island / Jones / Moriches / Shinnecock inlets
    ocean           South-shore ocean, offshore reefs, Montauk
    peconics        Peconic / Gardiners Bay, the Forks

Dependencies: Python 3 standard library only (urllib, re, html, json).

Usage:
    python3 li_report_scraper.py                 # -> ../data/li_report.json
    python3 li_report_scraper.py -o out.json     # custom output path
    python3 li_report_scraper.py --print         # print JSON to stdout only
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.request

REPORT_INDEX = "https://onthewater.com/regions/new-york"
UA = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# Long Island species we care about (lowercase match).
SPECIES = [
    "striped bass", "bass", "fluke", "porgy", "porgies", "sea bass",
    "black sea bass", "bluefish", "blues", "snapper", "weakfish",
    "blackfish", "tautog", "bonito", "false albacore", "albie", "albies",
    "mahi", "tuna", "bluefin", "yellowfin", "cod", "sea robin", "kingfish",
]

# Location (and keyword) -> waters class. Order matters: earlier classes win
# when a location could match more than one, so inlets/ocean beat the bays.
WATERS_RULES = [
    ("inlets", [
        "fire island inlet", "jones inlet", "moriches inlet",
        "shinnecock inlet", "rockaway inlet", "debs inlet", "inlet",
    ]),
    ("ocean", [
        "montauk", "offshore", "midshore", "canyon", "ocean", "atlantic",
        "fire island", "robert moses", "democrat point", "rockaway beach",
    ]),
    ("peconics", [
        "southold", "greenport", "orient", "peconic", "gardiners",
        "shelter island", "sag harbor", "noyack", "north fork", "riverhead",
        "mattituck", "cutchogue", "jamesport", "hampton bays",
    ]),
    ("south-shore-bays", [
        "great south bay", "south bay", "moriches", "shinnecock bay",
        "jamaica bay", "sheepshead", "brooklyn", "oakdale", "babylon",
        "bay shore", "freeport", "captree", "point lookout", "merrick",
        "amityville", "islip", "patchogue", "bellport", "south oyster bay",
    ]),
    ("north-shore", [
        "port washington", "northport", "huntington", "port jefferson",
        "smithtown", "stony brook", "mount sinai", "sea cliff", "glen cove",
        "oyster bay", "cold spring", "long island sound", "the sound",
        "manhasset", "roslyn", "bayville", "kings park", "nissequogue",
    ]),
]

AREA_LABELS = {
    "north-shore":      "LI Sound / North Shore",
    "south-shore-bays": "South Shore Bays",
    "inlets":           "Inlets",
    "ocean":            "Ocean / Beaches",
    "peconics":         "Peconics / The Forks",
    "unclassified":     "Long Island (general)",
}

MAX_REPORTS_PER_AREA = 3      # keep the feed small for the Pico
MAX_TEXT_CHARS = 220


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def latest_report_url(index_html):
    """Find the newest 'long-island-and-nyc-fishing-report-...' link."""
    links = re.findall(
        r'https://onthewater\.com/fishing-reports/\d{4}/\d{2}/'
        r'long-island-and-nyc-fishing-report-[a-z0-9-]+', index_html)
    # De-dup preserving order; the index lists newest first.
    seen, ordered = set(), []
    for l in links:
        if l not in seen:
            seen.add(l)
            ordered.append(l)
    return ordered[0] if ordered else None


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def classify(location, text):
    # Classify by the shop's home port first - it's the reliable signal.
    # A Moriches shop reporting on an offshore canyon trip is still "Moriches
    # waters" as far as a device sitting in that harbor is concerned. Only fall
    # back to the report text when we have no usable location.
    loc = location.lower().strip()
    if loc:
        for cls, keys in WATERS_RULES:
            for k in keys:
                if k in loc:
                    return cls
    low = text.lower()
    for cls, keys in WATERS_RULES:
        for k in keys:
            if k in low:
                return cls
    return "unclassified"


def find_species(text):
    low = text.lower()
    found = []
    for sp in SPECIES:
        if sp in low:
            # normalize a few plurals/synonyms
            norm = {"porgies": "porgy", "blues": "bluefish", "bass": "bass",
                    "albies": "false albacore", "albie": "false albacore",
                    "black sea bass": "sea bass", "tautog": "blackfish",
                    "bluefin": "tuna", "yellowfin": "tuna"}.get(sp, sp)
            if norm not in found:
                found.append(norm)
    # drop bare "bass" if "striped bass" already present
    if "striped bass" in found and "bass" in found:
        found.remove("bass")
    return found


def parse_reports(article_html):
    """Yield dicts {who, where, text} from the report body paragraphs."""
    start = article_html.find("entry-content")
    seg = article_html[start:] if start >= 0 else article_html
    seg = seg.split("Fishing Forecast")[0]  # cut the trailing forecast blurb
    paras = re.findall(r"<p[^>]*>(.*?)</p>", seg, re.S)
    out = []
    for p in paras:
        # Only real report paragraphs attribute a source ("... reports:"/
        # "reported:"). This skips embedded <script>/<style>/caption noise
        # whose stray quotes would otherwise look like a quoted body.
        if not re.search(r"report(?:s|ed)?\s*:", p, re.I):
            continue
        # who / where come from the RAW block (before stripping), so the
        # shop's linked <strong> and the "out of <strong>Location</strong>"
        # markers survive.
        strongs = [strip_tags(s) for s in
                   re.findall(r"<strong[^>]*>(.*?)</strong>", p, re.S)]
        strongs = [s for s in strongs if s]
        who = strongs[0] if strongs else ""
        where = ""
        m = re.search(r"out of\s*<strong[^>]*>(.*?)</strong>", p, re.S)
        if m:
            where = strip_tags(m.group(1))
        elif len(strongs) >= 2:
            where = strongs[1]
        # The report body is the curly-quoted text. Strip tags FIRST so that
        # href="..." attributes (straight quotes) can't be mistaken for it.
        clean = strip_tags(p)
        qm = re.search(r"“(.+?)”", clean, re.S)
        if not qm:
            continue
        text = qm.group(1).strip()
        # Reject non-prose payloads (CSS, bare URLs, embed markup).
        if len(text) < 40 or "://" in text or "font-family" in text.lower():
            continue
        if " " not in text or not re.search(r"[A-Za-z]{3}", text):
            continue
        out.append({"who": who, "where": where, "text": text})
    return out


def summarize(reports):
    """One-line area summary: top species + lead phrase."""
    counts = {}
    for r in reports:
        for sp in find_species(r["text"]):
            counts[sp] = counts.get(sp, 0) + 1
    top = sorted(counts, key=lambda s: -counts[s])[:3]
    lead = ""
    if reports:
        first = reports[0]["text"]
        lead = re.split(r"(?<=[.!?])\s", first)[0]
        if len(lead) > 120:
            lead = lead[:117] + "..."
    if top:
        return (", ".join(top).title()) + " active. " + lead
    return lead


def build_feed(report_url, article_html):
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', article_html)
    published = m.group(1) if m else None
    reports = parse_reports(article_html)

    areas = {}
    for r in reports:
        cls = classify(r["where"], r["text"])
        a = areas.setdefault(cls, {"label": AREA_LABELS[cls],
                                   "species": [], "reports": []})
        if len(a["reports"]) < MAX_REPORTS_PER_AREA:
            text = r["text"]
            if len(text) > MAX_TEXT_CHARS:
                text = text[:MAX_TEXT_CHARS - 3].rstrip() + "..."
            a["reports"].append({"where": r["where"], "who": r["who"],
                                 "text": text})
        for sp in find_species(r["text"]):
            if sp not in a["species"]:
                a["species"].append(sp)

    for cls, a in areas.items():
        if "striped bass" in a["species"] and "bass" in a["species"]:
            a["species"].remove("bass")
        a["summary"] = summarize([r for r in reports
                                  if classify(r["where"], r["text"]) == cls])

    return {
        "updated": published,
        "scraped_at": datetime.datetime.now(datetime.timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "On The Water - Long Island & NYC Fishing Report",
        "source_url": report_url,
        "areas": areas,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "data", "li_report.json")
    ap.add_argument("-o", "--out", default=default_out,
                    help="output JSON path (default ../data/li_report.json)")
    ap.add_argument("-u", "--url", default=None,
                    help="explicit report URL (default: latest from index)")
    ap.add_argument("--print", dest="to_stdout", action="store_true",
                    help="print JSON to stdout instead of writing a file")
    args = ap.parse_args()

    report_url = args.url
    if not report_url:
        print("[scraper] finding latest report...", file=sys.stderr)
        report_url = latest_report_url(fetch(REPORT_INDEX))
        if not report_url:
            print("[scraper] ERROR: could not find a report link", file=sys.stderr)
            return 2
    print("[scraper] fetching " + report_url, file=sys.stderr)
    feed = build_feed(report_url, fetch(report_url))

    n = sum(len(a["reports"]) for a in feed["areas"].values())
    print("[scraper] parsed %d reports across %d waters classes"
          % (n, len(feed["areas"])), file=sys.stderr)

    text = json.dumps(feed, indent=2, ensure_ascii=False)
    if args.to_stdout:
        print(text)
    else:
        out = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print("[scraper] wrote %s (%d bytes)" % (out, len(text)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
