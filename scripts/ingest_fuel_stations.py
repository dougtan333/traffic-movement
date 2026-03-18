"""
VIC Fuel Stations — Servo Saver Reference Data Loader

Loads fuel station reference data (stations + brands) from the
Service Victoria Servo Saver Open Data API into DuckDB.

Run once to populate fuel_stations, then periodically to pick up
new stations or metadata changes.

Usage:
  python scripts/ingest_fuel_stations.py

Requires: requests, duckdb, python-dotenv (optional)
API docs: https://service.vic.gov.au/-/media/bb0b5dbe245f443db4a90263090b6d88.pdf
"""

import os
import sys
import re
import uuid
from pathlib import Path

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


def get_consumer_id():
    load_dotenv()
    key = os.environ.get("SERVO_SAVER_CONSUMER_ID", "")
    if not key:
        print("ERROR: Set SERVO_SAVER_CONSUMER_ID in .env")
        sys.exit(1)
    return key


def api_get(endpoint, consumer_id):
    """Make authenticated GET request to the Servo Saver API."""
    headers = {
        "User-Agent": "AMIP/1.0",
        "x-consumer-id": consumer_id,
        "x-transactionid": str(uuid.uuid4()),
    }
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def parse_postcode(address):
    """Extract 4-digit postcode from an Australian address string.
    Formats seen: '276 Clyde Road, BERWICK, 3806' or '123 Main St, Melbourne VIC 3000'
    """
    if not address:
        return None
    m = re.search(r"\b(\d{4})\s*$", address.strip())
    return m.group(1) if m else None


def parse_suburb(address):
    """Extract suburb from address. Handles:
    - '276 Clyde Road, BERWICK, 3806'  (most common — suburb before postcode)
    - '123 Main St, Melbourne VIC 3000'
    """
    if not address:
        return None
    # Try format: stuff, SUBURB, POSTCODE
    m = re.search(r",\s*([A-Za-z\s-]+?)\s*,?\s*\d{4}\s*$", address.strip())
    if m:
        suburb = m.group(1).strip()
        # Remove "VIC" if present
        suburb = re.sub(r"\s*VIC\s*$", "", suburb, flags=re.IGNORECASE).strip()
        if suburb:
            return suburb.title()
    return None


def load_brands(consumer_id):
    """Fetch brand reference data. Returns {brand_id: {name, type}} dict."""
    print("  Fetching brands...")
    data = api_get("/fuel/reference-data/brands", consumer_id)
    brands = {}
    for b in data.get("brands", []):
        brands[b["id"]] = {"name": b["name"], "type": b.get("type", "")}
    print(f"  {len(brands)} brands loaded")
    return brands


def load_stations(con, consumer_id, brands):
    """Fetch all stations and upsert into fuel_stations table."""
    print("  Fetching stations...")
    data = api_get("/fuel/reference-data/stations", consumer_id)
    stations = data.get("fuelStations", [])
    print(f"  {len(stations)} stations returned from API")

    # Clear and reload (full refresh — station list can change)
    con.execute("DELETE FROM fuel_stations")

    inserted = 0
    for s in stations:
        sid = s.get("id", "")
        name = s.get("name", "")
        brand_id = s.get("brandId", "")
        address = s.get("address", "")
        phone = s.get("contactPhone")
        loc = s.get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        updated = s.get("updatedAt")

        brand = brands.get(brand_id, {})
        brand_name = brand.get("name", "")
        brand_type = brand.get("type", "")
        postcode = parse_postcode(address)
        suburb = parse_suburb(address)

        con.execute("""
            INSERT INTO fuel_stations (
                station_id, name, brand_id, brand_name, brand_type,
                address, postcode, suburb, latitude, longitude,
                contact_phone, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            sid, name, brand_id, brand_name, brand_type,
            address, postcode, suburb, lat, lon, phone, updated,
        ])
        inserted += 1

    print(f"  {inserted} stations loaded into fuel_stations")

    # Summary
    stats = con.execute("""
        SELECT count(*) as total,
               count(DISTINCT brand_name) as brands,
               count(DISTINCT postcode) as postcodes,
               count(CASE WHEN latitude IS NOT NULL THEN 1 END) as with_coords
        FROM fuel_stations
    """).fetchone()
    print(f"  {stats[0]} stations, {stats[1]} brands, {stats[2]} postcodes, {stats[3]} with coordinates")

    # Top brands by station count
    top = con.execute("""
        SELECT brand_name, brand_type, count(*) as n
        FROM fuel_stations
        WHERE brand_name != ''
        GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
    """).fetchall()
    print("  Top brands:")
    for r in top:
        print(f"    {r[0]:<20s} ({r[1]:<12s}) {r[2]:>4d} stations")


def main():
    consumer_id = get_consumer_id()
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Fuel Stations — DB: {DB_PATH}")

    brands = load_brands(consumer_id)
    load_stations(con, consumer_id, brands)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
