"""
VIC Fuel Prices — Servo Saver Twice-Daily Price Poller

Polls the Service Victoria Servo Saver Open Data API for current fuel prices
across all registered Victorian fuel stations. Stores AM and PM snapshots
in the fuel_prices table.

Data is 24-hour delayed from retailer submissions. Poll twice daily
(morning + afternoon) for outage tracking and price change detection.

Usage:
  python scripts/poll_fuel_prices.py                  # single poll (auto AM/PM)
  python scripts/poll_fuel_prices.py --period AM      # force AM snapshot
  python scripts/poll_fuel_prices.py --period PM      # force PM snapshot
  python scripts/poll_fuel_prices.py --loop            # poll every 12 hours

Requires: requests, duckdb
API rate limit: 10 requests per 60 seconds.
"""

import os
import sys
import uuid
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

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
POLL_INTERVAL = 43200  # 12 hours


def get_consumer_id():
    load_dotenv()
    key = os.environ.get("SERVO_SAVER_CONSUMER_ID", "")
    if not key:
        print("ERROR: Set SERVO_SAVER_CONSUMER_ID in .env")
        sys.exit(1)
    return key


def detect_period():
    """Auto-detect AM/PM based on current AEST time. Before 2pm = AM."""
    hour = datetime.now(AEST).hour
    return "AM" if hour < 14 else "PM"


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


def poll_once(con, consumer_id, period=None):
    """Fetch all fuel prices and store as a snapshot (AM or PM)."""
    now_aest = datetime.now(AEST)
    snapshot_date = now_aest.date()
    if period is None:
        period = detect_period()

    # Dedup: check (date, period) combination
    existing = con.execute(
        "SELECT count(*) FROM fuel_prices WHERE snapshot_date = ? AND snapshot_period = ?",
        [snapshot_date, period]
    ).fetchone()[0]
    if existing > 0:
        print(f"  Already have {existing} rows for {snapshot_date} {period}, skipping")
        return

    print(f"  Fetching fuel prices for {snapshot_date} {period}...")
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
                    price_cpl, is_available, retailer_updated_at,
                    snapshot_period
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [sid, snapshot_date, fuel_type, price, available, updated, period])
            inserted += 1

    print(f"  {inserted} price records stored for {snapshot_date} {period}")

    # Summary stats
    stats = con.execute("""
        SELECT fuel_type, count(*) as stations,
               round(avg(price_cpl), 1) as avg_price,
               round(min(price_cpl), 1) as min_price,
               round(max(price_cpl), 1) as max_price,
               sum(case when not is_available then 1 else 0 end) as unavailable
        FROM fuel_prices
        WHERE snapshot_date = ? AND snapshot_period = ?
        GROUP BY fuel_type
        ORDER BY stations DESC
    """, [snapshot_date, period]).fetchall()

    print(f"  {'Type':<6} {'Stations':>8} {'Avg':>8} {'Min':>8} {'Max':>8} {'Out':>5}")
    print(f"  {'-'*47}")
    for r in stats:
        avg_str = f"{r[2]:>7.1f}c" if r[2] is not None else "    N/A"
        min_str = f"{r[3]:>7.1f}c" if r[3] is not None else "    N/A"
        max_str = f"{r[4]:>7.1f}c" if r[4] is not None else "    N/A"
        print(f"  {r[0]:<6} {r[1]:>8} {avg_str} {min_str} {max_str} {r[5]:>5}")


def main():
    parser = argparse.ArgumentParser(description="Servo Saver fuel price poller")
    parser.add_argument("--loop", action="store_true", help="Poll every 12 hours")
    parser.add_argument("--period", choices=["AM", "PM"],
                        help="Force AM or PM snapshot (default: auto-detect)")
    args = parser.parse_args()

    consumer_id = get_consumer_id()
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Fuel Price Poller — DB: {DB_PATH}")

    if args.loop:
        print(f"Looping every {POLL_INTERVAL}s (12h). Ctrl+C to stop.")
        while True:
            try:
                poll_once(con, consumer_id, period=args.period)
            except Exception as e:
                print(f"  ERROR: {e}")
            time.sleep(POLL_INTERVAL)
    else:
        poll_once(con, consumer_id, period=args.period)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
