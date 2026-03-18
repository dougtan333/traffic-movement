"""
Brent Crude Oil + AUD/USD — Daily Refresh

Fetches daily Brent crude spot price from the US EIA API and the AUD/USD
exchange rate from the RBA, then updates the wholesale_prices table with:
  - brent_usd_bbl:  Brent crude USD per barrel
  - aud_usd_rate:   AUD/USD exchange rate
  - brent_aud_cpl:  Brent converted to AUD cents per litre

Conversion: 1 barrel = 158.987 litres
  brent_aud_cpl = (brent_usd / 158.987) / aud_usd * 100

Usage:
  python scripts/refresh_brent.py              # fetch latest + backfill
  python scripts/refresh_brent.py --backfill   # backfill all missing dates

Data sources:
  - EIA API v2: https://api.eia.gov/v2/petroleum/pri/spt/data/
  - RBA CSV: https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv
"""

import os
import sys
import csv
import io
from pathlib import Path
from datetime import datetime, date, timedelta

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
LITRES_PER_BARREL = 158.987

# EIA API v2 — Brent crude spot price (daily, USD/barrel)
EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

# RBA exchange rate CSV — contains daily AUD/USD
RBA_FX_URL = "https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"


def get_eia_key():
    load_dotenv()
    key = os.environ.get("EIA_API_KEY", "")
    if not key:
        print("ERROR: Set EIA_API_KEY in .env")
        sys.exit(1)
    return key


def fetch_brent_prices(api_key, start_date="2004-01-01"):
    """Fetch daily Brent crude spot prices from EIA API v2.
    Returns dict of {date_str: usd_per_barrel}.
    """
    print(f"  Fetching Brent crude from EIA (from {start_date})...")
    prices = {}
    offset = 0
    batch_size = 5000

    while True:
        params = {
            "api_key": api_key,
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": "RBRTE",  # Brent spot price
            "start": start_date,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": batch_size,
        }
        resp = requests.get(EIA_BASE, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("response", {}).get("data", [])
        if not rows:
            break

        for row in rows:
            period = row.get("period", "")
            value = row.get("value")
            if period and value is not None:
                try:
                    prices[period] = float(value)
                except (ValueError, TypeError):
                    pass

        offset += batch_size
        if len(rows) < batch_size:
            break

    print(f"  {len(prices)} daily Brent prices fetched")
    return prices


def fetch_aud_usd_rates():
    """Fetch daily AUD/USD exchange rates from RBA CSV.
    Returns dict of {date_str: aud_usd_rate}.
    The RBA CSV has a header row, description rows, then data.
    Column for USD is typically 'FXRUSD' (USD per 1 AUD).
    """
    print("  Fetching AUD/USD rates from RBA...")
    resp = requests.get(RBA_FX_URL, timeout=60)
    resp.raise_for_status()

    rates = {}
    lines = resp.text.splitlines()

    # Find the header row (starts with 'Series ID' or contains 'FXRUSD')
    header_idx = None
    usd_col = None
    for i, line in enumerate(lines):
        if "FXRUSD" in line:
            header_idx = i
            cols = line.split(",")
            for j, col in enumerate(cols):
                if "FXRUSD" in col:
                    usd_col = j
                    break
            break

    if header_idx is None or usd_col is None:
        print("  ERROR: Could not find FXRUSD column in RBA data")
        return rates

    # Parse data rows (after header)
    for line in lines[header_idx + 1:]:
        cols = line.split(",")
        if len(cols) <= usd_col:
            continue
        date_str = cols[0].strip()
        val_str = cols[usd_col].strip()
        if not date_str or not val_str:
            continue
        try:
            # RBA date format: DD-Mon-YYYY (e.g. 02-Jan-2024)
            dt = datetime.strptime(date_str, "%d-%b-%Y").date()
            rate = float(val_str)
            rates[dt.isoformat()] = rate
        except (ValueError, TypeError):
            continue

    print(f"  {len(rates)} daily AUD/USD rates fetched")
    return rates


def update_wholesale_prices(con, brent_prices, fx_rates):
    """Update wholesale_prices rows with Brent and AUD/USD data.
    Only updates rows that already exist (dates from AIP TGP data).
    Also inserts new rows for Brent dates not in the table.
    """
    existing_dates = set(
        r[0].isoformat() if isinstance(r[0], date) else str(r[0])
        for r in con.execute("SELECT date FROM wholesale_prices").fetchall()
    )

    updated = 0
    inserted = 0

    # Get all dates that have either Brent or FX data
    all_dates = sorted(set(list(brent_prices.keys()) + list(fx_rates.keys())))

    for dt_str in all_dates:
        brent = brent_prices.get(dt_str)
        fx = fx_rates.get(dt_str)

        # Calculate AUD cents per litre if we have both values
        brent_aud_cpl = None
        if brent is not None and fx is not None and fx > 0:
            brent_aud_cpl = round((brent / LITRES_PER_BARREL) / fx * 100, 1)

        if dt_str in existing_dates:
            # Update existing row
            con.execute("""
                UPDATE wholesale_prices
                SET brent_usd_bbl = COALESCE(?, brent_usd_bbl),
                    aud_usd_rate = COALESCE(?, aud_usd_rate),
                    brent_aud_cpl = COALESCE(?, brent_aud_cpl)
                WHERE date = ?
            """, [brent, fx, brent_aud_cpl, dt_str])
            updated += 1
        else:
            # Insert new row (Brent-only date, no TGP data)
            con.execute("""
                INSERT INTO wholesale_prices (date, brent_usd_bbl, aud_usd_rate, brent_aud_cpl)
                VALUES (?, ?, ?, ?)
            """, [dt_str, brent, fx, brent_aud_cpl])
            inserted += 1

    print(f"  Updated {updated} existing rows, inserted {inserted} new rows")

    # Show recent values
    latest = con.execute("""
        SELECT date, mel_ulp_tgp_cpl, brent_usd_bbl, aud_usd_rate, brent_aud_cpl
        FROM wholesale_prices
        WHERE brent_usd_bbl IS NOT NULL
        ORDER BY date DESC LIMIT 5
    """).fetchall()
    print(f"  Latest wholesale + Brent:")
    print(f"  {'Date':<12} {'Mel ULP':>8} {'Brent$':>8} {'AUD/USD':>8} {'Brent c/l':>10}")
    for r in latest:
        mel = f"{r[1]:.1f}" if r[1] else "—"
        brent = f"${r[2]:.2f}" if r[2] else "—"
        fx = f"{r[3]:.4f}" if r[3] else "—"
        bcpl = f"{r[4]:.1f}c" if r[4] else "—"
        print(f"  {r[0]}  {mel:>8} {brent:>8} {fx:>8} {bcpl:>10}")


def main():
    api_key = get_eia_key()
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Brent Crude + AUD/USD Refresh — DB: {DB_PATH}")

    # Find the earliest date in wholesale_prices to align Brent data
    earliest = con.execute("SELECT min(date) FROM wholesale_prices").fetchone()[0]
    start = str(earliest) if earliest else "2004-01-01"

    brent_prices = fetch_brent_prices(api_key, start_date=start)
    fx_rates = fetch_aud_usd_rates()
    update_wholesale_prices(con, brent_prices, fx_rates)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
