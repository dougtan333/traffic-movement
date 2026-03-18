"""
VIC Fuel Prices — Servo Saver Daily Price Poller

Polls the Service Victoria Servo Saver Open Data API for current fuel prices
across all registered Victorian fuel stations. Stores daily snapshots in
the fuel_prices table.

Data is 24-hour delayed from retailer submissions. Poll once daily (morning).

Usage:
  python scripts/poll_fuel_prices.py             # single poll
  python scripts/poll_fuel_prices.py --loop       # poll every 24 hours

Requires: requests, duckdb
API rate limit: 10 requests per 60 seconds.
"""

import os
import sys
import uuid
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta, date

import duckdb
import requests

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
BASE_URL = "https://api.fuel.service.vic.gov.au/open-data/v1"
AEST = timezone(timedelta(hours=10))
POLL_INTERVAL = 86400  # 24 hours


def get_consumer_id():
    load_dotenv()
    key = os.environ.get("SERVO_SAVER_CONSUMER_ID", "")
    if not key:
        print("ERROR: Set SERVO_SAVER_CONSUMER_ID in .env")
        sys.exit(1)
    return key


def api_get(endpoint, consumer_id):
    """Make authenticated GET request to Servo Saver API."""
    headers = {
        "User-Agent": "AMIP/1.0",
        "x-consumer-id": consumer_id,
        "x-transactionid": str(uuid.uuid4()),
    }
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()


def poll_once(con, consumer_id):
    """Fetch all fuel prices and store as a daily snapshot."""
    now_aest = datetime.now(AEST)
    snapshot_date = now_aest.date()

    # Check if we already have data for today
    existing = con.execute(
        "SELECT count(*) FROM fuel_prices WHERE snapshot_date = ?", [snapshot_date]
    ).fetchone()[0]
    if existing > 0:
        print(f"  Already have {existing} rows for {snapshot_date}, skipping")
        return

    print(f"  Fetching fuel prices for {snapshot_date}...")
    data = api_get("/fuel/prices", consumer_id)
    details = data.get("fuelPriceDetails", [])
    print(f"  {len(details)} stations returned")

    inserted = 0
    for station in details:
        sid = station.get("fuelStation", {}).get("id", "")
        prices = station.get("fuelPrices", [])
        for p in prices:
            fuel_type = p.get("fuelType", "")
            price = p.get("price")
            available = p.get("isAvailable", False)
            updated = p.get("updatedAt")

            con.execute("""
                INSERT INTO fuel_prices (
                    station_id, snapshot_date, fuel_type,
                    price_cpl, is_available, retailer_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [sid, snapshot_date, fuel_type, price, available, updated])
            inserted += 1

    print(f"  {inserted} price records stored for {snapshot_date}")

    # Summary stats
    stats = con.execute("""
        SELECT fuel_type, count(*) as stations,
               round(avg(price_cpl), 1) as avg_price,
               round(min(price_cpl), 1) as min_price,
               round(max(price_cpl), 1) as max_price
        FROM fuel_prices
        WHERE snapshot_date = ?
          AND is_available = true
          AND price_cpl > 0
        GROUP BY fuel_type
        ORDER BY stations DESC
    """, [snapshot_date]).fetchall()

    print(f"  {'Type':<6} {'Stations':>8} {'Avg':>8} {'Min':>8} {'Max':>8}")
    print(f"  {'-'*40}")
    for r in stats:
        print(f"  {r[0]:<6} {r[1]:>8} {r[2]:>7.1f}c {r[3]:>7.1f}c {r[4]:>7.1f}c")


def main():
    parser = argparse.ArgumentParser(description="Servo Saver fuel price poller")
    parser.add_argument("--loop", action="store_true", help="Poll every 24 hours")
    args = parser.parse_args()

    consumer_id = get_consumer_id()
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Fuel Price Poller — DB: {DB_PATH}")

    if args.loop:
        print(f"Looping every {POLL_INTERVAL}s (24h). Ctrl+C to stop.")
        while True:
            try:
                poll_once(con, consumer_id)
            except Exception as e:
                print(f"  ERROR: {e}")
            time.sleep(POLL_INTERVAL)
    else:
        poll_once(con, consumer_id)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
