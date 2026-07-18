# Third-Party Notices & Attributions

Worldwide-Tide-Astro.Info is © 2026 Maritime Credential Integrity Group LLC
(see LICENSE). It relies on the third-party data sources, services, and
algorithms listed below. Each remains the property of its owner and is governed
by its own terms — **the repository license grants no rights in any of them.**

## Data sources & services

| Source | Used for | Attribution / license | Notes |
|--------|----------|-----------------------|-------|
| **WorldTides** (worldtides.info) | Tide predictions | Requires an API key; governed by WorldTides' terms | Paid/keyed API. |
| **Open-Meteo** (open-meteo.com) | Weather, forecast, current wind/gust | Data under **CC BY 4.0**; attribution required | **Free for non-commercial use.** Commercial use requires an Open-Meteo API plan. |
| **Open-Meteo Marine** | Wave height/period, sea-surface temp | CC BY 4.0; attribution required | Same non-commercial terms as above. |
| **sunrise-sunset.org** | Sunrise/sunset/solar times | Free public API | — |
| **Nominatim / OpenStreetMap** (nominatim.openstreetmap.org) | Geocoding location search | Data **© OpenStreetMap contributors**, ODbL; subject to the Nominatim Usage Policy | The public endpoint is for light use only; commercial/bulk use requires self-hosting or a paid geocoder. |
| **timeapi.io** | Timezone offset by coordinate | Free public API | — |
| **Astronomical algorithms** | Moon rise/set, phase | Based on standard/Meeus formulas | Public-domain mathematics. |

## Fishing-report content

The optional Long Island fishing-report feature summarizes reports published by
**On The Water** (onthewater.com) and similar outlets. That report text is the
copyrighted property of its respective publishers.

- The scraper (`tools/li_report_scraper.py`) produces short, **attributed**
  excerpts for personal, informational use.
- This distilled feed is **NOT stored in or distributed with this repository.**
  It is hosted separately (a GitHub Gist / external location) and always carries
  its source attribution.
- `data/li_report.sample.json` contains only **fictional** sample content
  authored for this project to document the feed's schema.

## Commercial-use caveat

Several sources above are free for **personal / non-commercial** use only
(notably Open-Meteo and the public Nominatim endpoint), and republishing
third-party report content may implicate the publisher's terms. This project as
published is intended for personal and evaluation use. Any commercial
deployment by Maritime Credential Integrity Group LLC would require reviewing
and, where applicable, licensing these sources (e.g. an Open-Meteo commercial
plan, a commercial geocoder, and permission for any report content).
