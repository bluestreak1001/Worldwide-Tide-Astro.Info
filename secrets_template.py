# secrets_template.py
# Copy this file to secrets.py and fill in your real values.
# secrets.py is excluded from git via .gitignore — never commit it.

WIFI_SSID     = "your_wifi_network_name"
WIFI_PASSWORD = "your_wifi_password"

# Free API key from https://www.worldtides.info
WORLDTIDES_KEY = "your_worldtides_api_key"

# OPTIONAL - Long Island fishing-report feed.
# The heavy scraping runs off-device (see tools/li_report_scraper.py); it
# publishes a small li_report.json. Point this at wherever you host that file:
#   - a GitHub raw URL, e.g.
#     https://raw.githubusercontent.com/<user>/<repo>/main/data/li_report.json
#   - a gist raw URL, or a small web server on the Pi that runs the scraper.
# Leave "" to disable the local-report feature (the rest of the station still
# works, and the boating/fishing scores are computed on-device regardless).
REPORT_FEED_URL = ""
