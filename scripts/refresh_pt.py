"""
Refresh VIC public transport patronage data.

Downloads the two PT patronage CSVs from the VIC Open Data portal
(monthly totals + day-type breakdown) if the file size has changed,
then reloads into DuckDB. Full table replace — these are small CSVs.

Published with a 2-month lag. Updated monthly around the 20th.

Usage:
  python scripts/refresh_pt.py           # check and refresh if new
  python scripts/refresh_pt.py --force   # re-download regardless

Designed to run as part of daily_refresh.py pipeline.
"""

import argparse
import json
from pathlib import Path
from urllib.request import urlopen, Request

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
DATA_DIR = PROJECT_ROOT / "data_vic_new"
TRACKING_FILE = DATA_DIR / "pt_tracking.json"

# CKAN resource URLs (from discover.data.vic.gov.au API)
SOURCES = {
    "monthly": {
        "url": "https://opendata.transport.vic.gov.au/dataset/1ab35aa9-f21d-4f00-939b-60dade427d45/resource/d41a7a25-4397-48ed-af88-d7d424ec6dcc/download/monthly_public_transport_patronage_by_mode.csv",
        "file": "pt_patronage_monthly.csv",
    },
    "daytype": {
        "url": "https://opendata.transport.vic.gov.au/dataset/3937e4b1-2423-4b62-9bf0-62d36277ac55/resource/01366a15-0e75-4036-be60-b85b5fde042e/download/monthly_average_patronage_by_day_type_and_by_mode.csv",
        "file": "pt_patronage_daytype.csv",
    },
}


def load_tracking():
    if TRACKING_FILE.exists():
        return json.loads(TRACKING_FILE.read_text())
    return {}


def save_tracking(state):
    TRACKING_FILE.write_text(json.dumps(state, indent=2))


def get_remote_size(url):
    req = Request(url, method="HEAD")
    with urlopen(req, timeout=30) as resp:
        return int(resp.headers.get("Content-Length", 0))


def download_file(url, dest):
    req = Request(url)
    with urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def ingest_monthly(con, csv_path):
    """Full replace of pt_patronage_monthly."""
    con.execute("DELETE FROM pt_patronage_monthly")
    con.execute(f"""
        INSERT INTO pt_patronage_monthly
        SELECT
            "Year"::SMALLINT, "Month"::TINYINT, "Month name",
            "Metropolitan train"::BIGINT, "Metropolitan tram"::BIGINT,
            "Metropolitan bus"::BIGINT, "Regional train"::BIGINT,
            "Regional coach"::BIGINT, "Regional bus"::BIGINT
        FROM read_csv_auto('{csv_path}')
    """)
    count = con.execute("SELECT count(*) FROM pt_patronage_monthly").fetchone()[0]
    latest = con.execute("SELECT year, month_name FROM pt_patronage_monthly ORDER BY year DESC, month DESC LIMIT 1").fetchone()
    print(f"  pt_patronage_monthly: {count} rows, latest: {latest[1]} {latest[0]}")


def ingest_daytype(con, csv_path):
    """Full replace of pt_patronage_daytype."""
    con.execute("DELETE FROM pt_patronage_daytype")
    con.execute(f"""
        INSERT INTO pt_patronage_daytype
        SELECT
            "Year"::SMALLINT, "Month"::TINYINT, "Month_name",
            "Day_of_week", "Day_type", "Mode", "Pax_daily"::INTEGER
        FROM read_csv_auto('{csv_path}')
    """)
    count = con.execute("SELECT count(*) FROM pt_patronage_daytype").fetchone()[0]
    print(f"  pt_patronage_daytype: {count} rows")


def main():
    parser = argparse.ArgumentParser(description="Refresh PT patronage data")
    parser.add_argument("--force", action="store_true", help="Re-download regardless")
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    tracking = load_tracking()

    # Check if either CSV has changed
    any_changed = False
    for key, src in SOURCES.items():
        remote_size = get_remote_size(src["url"])
        prev_size = tracking.get(key, {}).get("size", 0)
        if args.force or remote_size != prev_size:
            print(f"  {key}: {remote_size:,d} bytes (was {prev_size:,d}) — downloading")
            csv_path = DATA_DIR / src["file"]
            download_file(src["url"], csv_path)
            tracking[key] = {"size": remote_size}
            any_changed = True
        else:
            print(f"  {key}: unchanged ({remote_size:,d} bytes) — skip")

    if not any_changed:
        print("PT patronage data is up to date.")
        save_tracking(tracking)
        return

    # Ingest updated CSVs
    con = duckdb.connect(str(DB_PATH))

    monthly_path = DATA_DIR / SOURCES["monthly"]["file"]
    daytype_path = DATA_DIR / SOURCES["daytype"]["file"]

    if monthly_path.exists():
        ingest_monthly(con, monthly_path)
    if daytype_path.exists():
        ingest_daytype(con, daytype_path)

    con.execute("FORCE CHECKPOINT")
    con.close()
    save_tracking(tracking)
    print("PT patronage refresh complete.")


if __name__ == "__main__":
    main()
