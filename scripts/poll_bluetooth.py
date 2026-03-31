"""
VIC Bluetooth Travel Time — Polling Script

Polls the Transport Victoria Bluetooth Travel Time API every 5 minutes,
storing speed/travel-time snapshots in the speed_observations table and
route reference data in bluetooth_routes.

First run fetches routes + links, populates bluetooth_routes, then polls.
Subsequent runs just poll and append to speed_observations.

Usage:
  1. Set your API key in .env: VIC_BLUETOOTH_API_KEY=your_key
  2. Run:  python scripts/poll_bluetooth.py          (single poll)
  3. Loop: python scripts/poll_bluetooth.py --loop    (every 5 min)

Requires: requests, duckdb, python-dotenv
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import duckdb
import requests

try:
    from dotenv import load_dotenv
except ImportError:
    # If python-dotenv not installed, read .env manually
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
BASE_URL = "https://api.opendata.transport.vic.gov.au/opendata/roads/bluetooth-travel-time/v1"
AEST = timezone(timedelta(hours=10))
POLL_INTERVAL = 300  # 5 minutes


def get_api_key():
    load_dotenv()
    key = os.environ.get("VIC_BLUETOOTH_API_KEY", "")
    if not key or key == "your_key_here":
        print("ERROR: Set VIC_BLUETOOTH_API_KEY in .env")
        sys.exit(1)
    return key


def api_get(path, api_key):
    """Make authenticated GET request to the Bluetooth API."""
    url = f"{BASE_URL}{path}"
    headers = {"KeyId": api_key}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_and_store_routes(con, api_key):
    """
    Fetch all Bluetooth routes from the API and store in bluetooth_routes.
    Only runs if the table is empty.
    """
    existing = con.execute("SELECT count(*) FROM bluetooth_routes").fetchone()[0]
    if existing > 0:
        print(f"  bluetooth_routes already has {existing} routes — skipping fetch")
        return

    print("  Fetching routes from API...")
    data = api_get("/routes", api_key)

    # The response structure may vary — handle both list and dict formats
    routes = data if isinstance(data, list) else data.get("routes", data.get("features", []))

    inserted = 0
    for route in routes:
        # Extract fields — adapt to actual response structure
        route_id = str(route.get("routeId", route.get("route_id", route.get("id", ""))))
        if not route_id:
            continue

        route_name = route.get("routeName", route.get("route_name", route.get("name", "")))
        primary_road = route.get("primaryRoadName", route.get("primary_road_name", ""))
        start_end = route.get("startEndDescription", route.get("start_end_description", ""))
        length_m = route.get("length", route.get("routeLength", None))
        direction = route.get("direction", "")

        # Geometry — may be nested
        geom = route.get("geometry", route.get("geopath", None))
        geom_json = json.dumps(geom) if geom else None

        con.execute("""
            INSERT OR IGNORE INTO bluetooth_routes
            (route_id, route_name, primary_road_name, start_end_desc, length_m, geometry_geojson, direction)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [route_id, route_name, primary_road, start_end, length_m, geom_json, direction])
        inserted += 1

    print(f"  Inserted {inserted} routes into bluetooth_routes")


def poll_links(con, api_key):
    """
    Fetch all Bluetooth links with current speed/travel-time stats.
    Each link is a segment between two Bluetooth receivers.
    Appends one row per link to speed_observations.
    """
    now_aest = datetime.now(AEST)
    ts_rounded = now_aest.replace(second=0, microsecond=0)
    ts_rounded = ts_rounded.replace(minute=(ts_rounded.minute // 5) * 5)
    now_aest_str = ts_rounded.strftime("%Y-%m-%d %H:%M:%S")

    print(f"  Polling links at {now_aest_str} AEST...")

    # Try fetching all links in one call
    try:
        data = api_get("/links", api_key)
    except requests.exceptions.HTTPError as e:
        # If /links doesn't work, try individual route links
        if e.response.status_code == 404:
            print("  /links endpoint not found — trying individual link IDs...")
            data = None
        else:
            raise

    if data is None:
        print("  WARNING: Could not fetch link data")
        return 0

    # API returns a flat list of link objects
    links = data if isinstance(data, list) else data.get("links", [])

    inserted = 0
    for link in links:
        link_id = str(link.get("id", ""))
        if not link_id:
            continue

        stats = link.get("latest_stats")
        if not stats:
            continue

        speed = stats.get("speed")
        travel_time = stats.get("travel_time")
        delay = stats.get("delay")
        excess_delay = stats.get("excess_delay")
        data_status = stats.get("data_status", "unknown")
        length_m = link.get("length")

        # Use the API's interval_start timestamp if available
        interval_ts = stats.get("interval_start")
        if interval_ts:
            # Parse ISO format and convert to naive AEST string
            from datetime import datetime as dt
            try:
                parsed = dt.fromisoformat(interval_ts)
                ts_str = parsed.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                ts_str = now_aest_str
        else:
            ts_str = now_aest_str

        # Skip if no useful data
        if speed is None and travel_time is None:
            continue

        speed_int = int(round(speed)) if speed is not None else None
        tt_int = int(round(travel_time)) if travel_time is not None else None
        delay_int = int(round(delay)) if delay is not None else None
        # Use excess_delay as congestion proxy — clamp to schema range
        cong_float = round(max(-99.99, min(99.99, float(excess_delay))), 2) if excess_delay is not None else None
        length_int = int(round(length_m)) if length_m is not None else None

        try:
            con.execute("""
                INSERT OR IGNORE INTO speed_observations
                (route_id, ts_interval, speed_kmh, travel_time_sec, delay_sec,
                 congestion_index, data_status, route_length_m)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [link_id, ts_str, speed_int, tt_int, delay_int,
                  cong_float, data_status, length_int])
            inserted += 1
        except Exception as e:
            print(f"  WARNING: Failed to insert link {link_id}: {e}")

    print(f"  Stored {inserted} speed observations for {now_aest_str}")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Poll VIC Bluetooth Travel Time API")
    parser.add_argument("--loop", action="store_true", help="Run continuously every 5 minutes")
    args = parser.parse_args()

    api_key = get_api_key()

    print(f"AMIP Bluetooth Poller — DB: {DB_PATH}")
    print(f"API base: {BASE_URL}")

    # First run: fetch route reference data (connect/disconnect immediately)
    con = duckdb.connect(str(DB_PATH))
    fetch_and_store_routes(con, api_key)
    con.execute("CHECKPOINT")
    con.close()

    if args.loop:
        print(f"\nStarting continuous polling (every {POLL_INTERVAL}s). Ctrl+C to stop.\n")
        while True:
            con = None
            try:
                con = duckdb.connect(str(DB_PATH))
                poll_links(con, api_key)
                con.execute("CHECKPOINT")
            except requests.exceptions.RequestException as e:
                print(f"  NETWORK ERROR: {e} — will retry in {POLL_INTERVAL}s")
            except duckdb.IOException as e:
                print(f"  DB LOCK ERROR: {e} — will retry in {POLL_INTERVAL}s")
            except Exception as e:
                print(f"  ERROR: {e} — will retry in {POLL_INTERVAL}s")
            finally:
                if con is not None:
                    try:
                        con.close()
                    except Exception:
                        pass
            time.sleep(POLL_INTERVAL)
    else:
        con = duckdb.connect(str(DB_PATH))
        poll_links(con, api_key)
        con.execute("CHECKPOINT")
        con.close()

    print("Done.")


if __name__ == "__main__":
    main()
