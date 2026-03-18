"""
AIP Wholesale Prices — Ingestion + Scrape Refresh

Two modes:
  1. SEED:    Load historical daily TGP from AIP Excel file (years of data)
  2. REFRESH: Scrape api.aip.com.au/public/tgpTables for latest 5 trading days

Seeds wholesale_prices table from AIP_TGP_Data Excel (Petrol TGP + Diesel TGP sheets).
Refresh appends any new dates not already in the table.

Brent crude and AUD/USD are handled separately by refresh_brent.py.

Usage:
  python scripts/ingest_wholesale_prices.py --seed     # one-time Excel load
  python scripts/ingest_wholesale_prices.py --refresh   # scrape latest 5 days
  python scripts/ingest_wholesale_prices.py             # defaults to refresh

Data source: Australian Institute of Petroleum (AIP)
  - Excel: https://www.aip.com.au/historical-ulp-and-diesel-tgp-data
  - HTML:  http://api.aip.com.au/public/tgpTables
"""

import sys
import re
import argparse
from pathlib import Path
from datetime import datetime, date

import duckdb
import openpyxl

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
DATA_DIR = PROJECT_ROOT / "data_vic_new"
AIP_TGP_TABLE_URL = "http://api.aip.com.au/public/tgpTables"

# Column indexes in the AIP Excel (after header row):
# 0=Date, 1=Sydney, 2=Melbourne, 3=Brisbane, 4=Adelaide, 5=Perth, 6=Darwin, 7=Hobart, 8=National Average
COL_DATE = 0
COL_SYD = 1
COL_MEL = 2
COL_NATIONAL = 8


def parse_excel_sheet(ws):
    """Parse an AIP TGP sheet into list of (date, sydney, melbourne, national) tuples."""
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):  # skip header
        dt = row[COL_DATE]
        if dt is None:
            continue
        if isinstance(dt, datetime):
            dt = dt.date()
        elif isinstance(dt, str):
            try:
                dt = datetime.strptime(dt, "%Y-%m-%d").date()
            except ValueError:
                continue
        if not isinstance(dt, date):
            continue

        syd = row[COL_SYD] if row[COL_SYD] is not None else None
        mel = row[COL_MEL] if row[COL_MEL] is not None else None
        nat = row[COL_NATIONAL] if row[COL_NATIONAL] is not None else None
        rows.append((dt, syd, mel, nat))
    return rows


def seed_from_excel(con):
    """Load historical TGP from AIP Excel file. Clears table first."""
    excel_files = sorted(DATA_DIR.glob("AIP_TGP_Data_*.xlsx"))
    if not excel_files:
        print("ERROR: No AIP_TGP_Data_*.xlsx found in", DATA_DIR)
        sys.exit(1)

    excel_path = excel_files[-1]
    print(f"Seeding wholesale_prices from: {excel_path.name}")

    wb = openpyxl.load_workbook(str(excel_path), read_only=True, data_only=True)

    # Parse petrol sheet
    petrol_ws = wb["Petrol TGP"]
    petrol_rows = parse_excel_sheet(petrol_ws)
    print(f"  Petrol TGP: {len(petrol_rows)} trading days ({petrol_rows[0][0]} to {petrol_rows[-1][0]})")

    # Parse diesel sheet
    diesel_ws = wb["Diesel TGP"]
    diesel_rows = parse_excel_sheet(diesel_ws)
    print(f"  Diesel TGP: {len(diesel_rows)} trading days ({diesel_rows[0][0]} to {diesel_rows[-1][0]})")
    wb.close()

    # Build a dict keyed by date with petrol + diesel values
    combined = {}
    for dt, syd, mel, nat in petrol_rows:
        combined[dt] = {
            "syd_ulp": syd, "mel_ulp": mel, "nat_ulp": nat,
            "syd_dsl": None, "mel_dsl": None, "nat_dsl": None,
        }
    for dt, syd, mel, nat in diesel_rows:
        if dt in combined:
            combined[dt]["syd_dsl"] = syd
            combined[dt]["mel_dsl"] = mel
            combined[dt]["nat_dsl"] = nat
        else:
            combined[dt] = {
                "syd_ulp": None, "mel_ulp": None, "nat_ulp": None,
                "syd_dsl": syd, "mel_dsl": mel, "nat_dsl": nat,
            }

    # Clear and reload
    con.execute("DELETE FROM wholesale_prices")

    insert_sql = """
        INSERT INTO wholesale_prices (
            date, mel_ulp_tgp_cpl, mel_diesel_tgp_cpl,
            syd_ulp_tgp_cpl, national_ulp_tgp_cpl, national_diesel_tgp_cpl
        ) VALUES (?, ?, ?, ?, ?, ?)
    """
    rows_inserted = 0
    for dt in sorted(combined.keys()):
        d = combined[dt]
        con.execute(insert_sql, [dt, d["mel_ulp"], d["mel_dsl"], d["syd_ulp"], d["nat_ulp"], d["nat_dsl"]])
        rows_inserted += 1

    print(f"  Loaded {rows_inserted} trading days into wholesale_prices")

    # Summary
    result = con.execute("""
        SELECT min(date), max(date), count(*),
               round(avg(mel_ulp_tgp_cpl), 1) as avg_mel_ulp
        FROM wholesale_prices
    """).fetchone()
    print(f"  Range: {result[0]} to {result[1]} ({result[2]} days, avg Melbourne ULP: {result[3]} c/l)")


def refresh_from_scrape(con):
    """Scrape the AIP TGP tables page for the latest 5 trading days. Appends new dates only."""
    if requests is None or BeautifulSoup is None:
        print("ERROR: requests and beautifulsoup4 are required for --refresh")
        print("  pip install requests beautifulsoup4")
        sys.exit(1)

    print(f"Scraping AIP TGP table: {AIP_TGP_TABLE_URL}")
    resp = requests.get(AIP_TGP_TABLE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find both tables (Petrol ULP, then Diesel)
    tables = soup.find_all("table")
    if len(tables) < 2:
        print("ERROR: Expected 2 tables (Petrol + Diesel), found", len(tables))
        sys.exit(1)

    def parse_aip_table(table):
        """Parse an AIP HTML table into {date: {city: value}} dict.
        
        Table structure: first row has th cells for dates (first th is empty).
        Data rows have a th cell for city name, then td cells for values.
        """
        data = {}

        # Get date columns from the first row's th elements
        header_row = table.find("tr")
        date_cols = []
        for th in header_row.find_all("th"):
            txt = th.get_text(strip=True)
            m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", txt)
            if m:
                day, month_name, year = m.groups()
                dt = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date()
                date_cols.append(dt)

        # Parse data rows — city in th, values in td
        for row in table.find_all("tr")[1:]:  # skip header row
            city_th = row.find("th")
            if not city_th:
                continue
            city = city_th.get_text(strip=True)
            cells = row.find_all("td")
            for i, cell in enumerate(cells):
                if i < len(date_cols):
                    try:
                        val = float(cell.get_text(strip=True))
                    except ValueError:
                        val = None
                    dt = date_cols[i]
                    if dt not in data:
                        data[dt] = {}
                    data[dt][city] = val
        return data

    petrol_data = parse_aip_table(tables[0])
    diesel_data = parse_aip_table(tables[1])

    all_dates = sorted(set(list(petrol_data.keys()) + list(diesel_data.keys())))
    print(f"  Found {len(all_dates)} trading days: {all_dates[0]} to {all_dates[-1]}")

    # Check which dates are already in the table
    existing = set(r[0] for r in con.execute("SELECT date FROM wholesale_prices").fetchall())

    inserted = 0
    for dt in all_dates:
        if dt in existing:
            continue
        p = petrol_data.get(dt, {})
        d = diesel_data.get(dt, {})
        con.execute("""
            INSERT INTO wholesale_prices (
                date, mel_ulp_tgp_cpl, mel_diesel_tgp_cpl,
                syd_ulp_tgp_cpl, national_ulp_tgp_cpl, national_diesel_tgp_cpl
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, [
            dt,
            p.get("Melbourne"), d.get("Melbourne"),
            p.get("Sydney"), None, None,  # national avg not in the HTML table
        ])
        inserted += 1

    print(f"  Inserted {inserted} new trading days (skipped {len(all_dates) - inserted} existing)")

    # Show latest values
    latest = con.execute("""
        SELECT date, mel_ulp_tgp_cpl, mel_diesel_tgp_cpl
        FROM wholesale_prices ORDER BY date DESC LIMIT 3
    """).fetchall()
    for r in latest:
        print(f"    {r[0]}: ULP {r[1]} c/l, Diesel {r[2]} c/l")


def main():
    parser = argparse.ArgumentParser(description="AIP wholesale price ingestion")
    parser.add_argument("--seed", action="store_true", help="Seed from AIP Excel file (one-time)")
    parser.add_argument("--refresh", action="store_true", help="Scrape latest 5 days from AIP website")
    args = parser.parse_args()

    # Default to refresh if neither flag given
    if not args.seed and not args.refresh:
        args.refresh = True

    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Wholesale Prices — DB: {DB_PATH}")

    if args.seed:
        seed_from_excel(con)

    if args.refresh:
        refresh_from_scrape(con)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
