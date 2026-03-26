"""
Standalone Bluetooth Speed Archive Poller

Completely independent of the AMIP build. Polls the VIC Bluetooth
Travel Time API every 5 minutes and appends to its own DuckDB file.
Safe to run alongside the AMIP poller — both read the same API,
write to different databases.

Usage:
  python3 bluetooth_archive.py              # single poll
  python3 bluetooth_archive.py --loop       # continuous (every 5 min)

Requires: requests, duckdb
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import duckdb
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "bluetooth_archive.duckdb"
LOG_PATH = SCRIPT_DIR / "logs" / "archive.log"
ENV_PATH = SCRIPT_DIR.parent / ".env"  # reads API key from parent project .env

BASE_URL = "https://api.opendata.transport.vic.gov.au/opendata/roads/bluetooth-travel-time/v1"
AEST = timezone(timedelta(hours=10))
POLL_INTERVAL = 300  # 5 minutes


def load_api_key():
    """Read VIC_BLUETOOTH_API_KEY from parent project .env file."""
    if not ENV_PATH.exists():
        print(f"ERROR: No .env file at {ENV_PATH}")
        sys.exit(1)
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == "VIC_BLUETOOTH_API_KEY":
                val = v.strip()
                if val and val != "your_key_here":
                    return val
    print("ERROR: VIC_BLUETOOTH_API_KEY not found in .env")
    sys.exit(1)


def init_db():
    """Create the archive DB and table if they don't exist."""
    con = duckdb.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS speed_log (
            link_id    VARCHAR,
            ts         TIMESTAMP,
            speed_kmh  SMALLINT,
            tt_sec     INTEGER,
            delay_sec  INTEGER,
            congestion DECIMAL(6,2),
            status     VARCHAR,
            length_m   INTEGER,
            PRIMARY KEY (link_id, ts)
        )
    """)
    con.close()
    return True


def poll(api_key):
    """Fetch all links from the API and insert into archive DB."""
    now_aest = datetime.now(AEST)
    ts_rounded = now_aest.replace(second=0, microsecond=0)
    ts_rounded = ts_rounded.replace(minute=(ts_rounded.minute // 5) * 5)
    ts_str = ts_rounded.strftime("%Y-%m-%d %H:%M:%S")

    headers = {"KeyId": api_key}
    resp = requests.get(f"{BASE_URL}/links", headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    links = data if isinstance(data, list) else data.get("links", [])

    con = duckdb.connect(str(DB_PATH))
    inserted = 0

    for link in links:
        link_id = str(link.get("id", ""))
        if not link_id:
            continue
        stats = link.get("latest_stats")
        if not stats:
            continue

        speed = stats.get("speed")
        tt = stats.get("travel_time")
        if speed is None and tt is None:
            continue

        # Use the API's interval_start if available
        interval_ts = stats.get("interval_start")
        if interval_ts:
            try:
                parsed = datetime.fromisoformat(interval_ts)
                row_ts = parsed.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                row_ts = ts_str
        else:
            row_ts = ts_str

        speed_int = int(round(speed)) if speed is not None else None
        tt_int = int(round(tt)) if tt is not None else None
        delay_int = int(round(stats.get("delay", 0))) if stats.get("delay") is not None else None
        excess = stats.get("excess_delay")
        cong = round(max(-99.99, min(99.99, float(excess))), 2) if excess is not None else None
        status = stats.get("data_status", "unknown")
        length_m = int(round(link.get("length", 0))) if link.get("length") is not None else None

        try:
            con.execute("""
                INSERT OR IGNORE INTO speed_log
                (link_id, ts, speed_kmh, tt_sec, delay_sec, congestion, status, length_m)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [link_id, row_ts, speed_int, tt_int, delay_int, cong, status, length_m])
            inserted += 1
        except Exception as e:
            print(f"  WARN: {link_id}: {e}")

    con.close()
    return inserted, ts_str


def main():
    parser = argparse.ArgumentParser(description="Standalone Bluetooth speed archive")
    parser.add_argument("--loop", action="store_true", help="Poll continuously every 5 min")
    args = parser.parse_args()

    api_key = load_api_key()
    init_db()

    print(f"Bluetooth Archive Poller")
    print(f"  DB: {DB_PATH}")
    print(f"  API key: ...{api_key[-6:]}")

    if args.loop:
        print(f"  Mode: continuous (every {POLL_INTERVAL}s)\n")
        while True:
            try:
                count, ts = poll(api_key)
                print(f"  {ts}  stored {count} readings")
            except requests.exceptions.RequestException as e:
                print(f"  NETWORK ERROR: {e}")
            except Exception as e:
                print(f"  ERROR: {e}")
            time.sleep(POLL_INTERVAL)
    else:
        count, ts = poll(api_key)
        print(f"  {ts}  stored {count} readings")


if __name__ == "__main__":
    main()
