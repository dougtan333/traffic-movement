"""
Aviation Data Ingestion — BITRE Airport Traffic, Routes & OTP

Downloads four CSV files from data.gov.au (BITRE open data), filters to
2024+ and the five AMIP capital-city airports, then loads into DuckDB:

  - airport_monthly:     Merged passengers + aircraft movements per airport/month
  - domestic_routes:     City-pair route stats (passengers, load factor, seats)
  - aviation_otp:        On-time performance per route/month (All Airlines only)

Data sources:
  - BITRE Airport Traffic Data (CC-BY 3.0 AU)
    https://data.gov.au/data/dataset/airport-traffic-data
  - BITRE Domestic Airlines Top Routes & Totals (CC-BY 3.0 AU)
    https://data.gov.au/data/dataset/domestic-airlines-top-routes-and-totals
  - BITRE Domestic Airlines On Time Performance (CC-BY 3.0 AU)
    https://data.gov.au/data/dataset/domestic-airline-on-time-performance

Usage:
  python scripts/ingest_aviation.py
"""

import csv
import io
from pathlib import Path

import duckdb
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
DATA_DIR = PROJECT_ROOT / "data" / "aviation"

# Minimum year to ingest — keeps the DB skinny
MIN_YEAR = 2024

# Five AMIP capital-city airports — names as they appear in BITRE CSVs
AIRPORTS = {"ADELAIDE", "BRISBANE", "MELBOURNE", "PERTH", "SYDNEY"}

# City names as they appear in the routes/OTP data (departing/arriving ports)
CITIES = {"Adelaide", "Brisbane", "Melbourne", "Perth", "Sydney",
          "ADELAIDE", "BRISBANE", "MELBOURNE", "PERTH", "SYDNEY"}

# Download URLs (data.gov.au hosted CSVs, no auth required)
URLS = {
    "mon_pax": (
        "https://data.gov.au/data/dataset/cc5d888f-5850-47f3-815d-08289b22f5a8/"
        "resource/38bdc971-cb22-4894-b19a-814afc4e8164/download/mon_pax_web.csv"
    ),
    "mon_acm": (
        "https://data.gov.au/data/dataset/cc5d888f-5850-47f3-815d-08289b22f5a8/"
        "resource/583be26d-59b9-4bcc-827d-4d9f7162fb04/download/mon_acm_web.csv"
    ),
    "routes": (
        "https://data.gov.au/data/dataset/c5029f2a-39b3-4aef-8ae1-73e7962f6170/"
        "resource/677d307f-6a1f-4de4-9b85-5e1aa7074423/download/dom_citypairs_web.csv"
    ),
    "otp": (
        "https://data.gov.au/data/dataset/29128ebd-dbaa-4ff5-8b86-d9f30de56452/"
        "resource/cf663ed1-0c5e-497f-aea9-e74bfda9cf44/download/otp_time_series_web.csv"
    ),
}


def download_csv(name: str) -> list[dict]:
    """Download a CSV from BITRE/data.gov.au and return rows as dicts."""
    url = URLS[name]
    print(f"  Downloading {name}...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    print(f"  {len(rows):,} rows downloaded")
    return rows


def save_csv_locally(name: str, rows: list[dict]) -> None:
    """Cache raw CSV locally for inspection/reprocessing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.csv"
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {path}")


def create_aviation_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create aviation tables. Idempotent — uses IF NOT EXISTS."""

    # airport_monthly: merged passengers + aircraft movements per airport per month
    # One row per airport per month. Domestic/international split for both pax and movements.
    con.execute("""
        CREATE TABLE IF NOT EXISTS airport_monthly (
            airport         VARCHAR     NOT NULL,
            year            SMALLINT    NOT NULL,
            month           TINYINT     NOT NULL,
            dom_pax_in      INTEGER,
            dom_pax_out     INTEGER,
            dom_pax_total   INTEGER,
            int_pax_in      INTEGER,
            int_pax_out     INTEGER,
            int_pax_total   INTEGER,
            pax_total       INTEGER,
            dom_acm_in      INTEGER,
            dom_acm_out     INTEGER,
            dom_acm_total   INTEGER,
            int_acm_in      INTEGER,
            int_acm_out     INTEGER,
            int_acm_total   INTEGER,
            acm_total       INTEGER,
            PRIMARY KEY (airport, year, month)
        );
    """)

    # domestic_routes: city-pair route stats per month
    # Passengers, aircraft trips, load factor, distance, RPK, ASK, seats.
    con.execute("""
        CREATE TABLE IF NOT EXISTS domestic_routes (
            city1               VARCHAR     NOT NULL,
            city2               VARCHAR     NOT NULL,
            year                SMALLINT    NOT NULL,
            month               TINYINT     NOT NULL,
            passenger_trips     INTEGER,
            aircraft_trips      INTEGER,
            load_factor_pct     DECIMAL(5,1),
            distance_km         INTEGER,
            rpks                BIGINT,
            asks                BIGINT,
            seats               INTEGER,
            PRIMARY KEY (city1, city2, year, month)
        );
    """)

    # aviation_otp: on-time performance per route per month (All Airlines only)
    con.execute("""
        CREATE TABLE IF NOT EXISTS aviation_otp (
            route               VARCHAR     NOT NULL,
            departing_port      VARCHAR     NOT NULL,
            arriving_port       VARCHAR     NOT NULL,
            year                SMALLINT    NOT NULL,
            month               TINYINT     NOT NULL,
            sectors_scheduled   INTEGER,
            sectors_flown       INTEGER,
            cancellations       INTEGER,
            departures_on_time  INTEGER,
            arrivals_on_time    INTEGER,
            departures_delayed  INTEGER,
            arrivals_delayed    INTEGER,
            PRIMARY KEY (route, year, month)
        );
    """)
    print("  Aviation tables created/verified")


def safe_int(val: str) -> int | None:
    """Parse an integer from CSV, returning None for empty/invalid values."""
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def safe_float(val: str) -> float | None:
    """Parse a float from CSV, returning None for empty/invalid values."""
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except ValueError:
        return None


def ingest_airport_monthly(con: duckdb.DuckDBPyConnection) -> None:
    """Download pax + aircraft CSVs, merge, filter, and load into airport_monthly."""
    pax_rows = download_csv("mon_pax")
    acm_rows = download_csv("mon_acm")
    save_csv_locally("mon_pax", pax_rows)
    save_csv_locally("mon_acm", acm_rows)

    # Index aircraft movements by (airport, year, month) for merge
    acm_index = {}
    for r in acm_rows:
        key = (r["AIRPORT"].strip(), r["Year"].strip(), r["Month"].strip())
        acm_index[key] = r

    # Clear existing data and re-insert (full refresh, tiny table)
    con.execute("DELETE FROM airport_monthly")

    inserted = 0
    for r in pax_rows:
        airport = r["AIRPORT"].strip()
        year = safe_int(r["Year"])
        month = safe_int(r["Month"])
        if airport not in AIRPORTS or year is None or year < MIN_YEAR:
            continue

        # Look up matching aircraft movement row
        acm = acm_index.get((airport, r["Year"].strip(), r["Month"].strip()), {})

        con.execute("""
            INSERT INTO airport_monthly VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            airport, year, month,
            safe_int(r.get("Dom_Pax_In")),
            safe_int(r.get("Dom_Pax_Out")),
            safe_int(r.get("Dom_Pax_Total")),
            safe_int(r.get("Int_Pax_In")),
            safe_int(r.get("Int_Pax_Out")),
            safe_int(r.get("Int_Pax_Total")),
            safe_int(r.get("Pax_Total")),
            safe_int(acm.get("Dom_Acm_In")),
            safe_int(acm.get("Dom_Acm_Out")),
            safe_int(acm.get("Dom_Acm_Total")),
            safe_int(acm.get("Int_Acm_In")),
            safe_int(acm.get("Int_Acm_Out")),
            safe_int(acm.get("Int_Acm_Total")),
            safe_int(acm.get("Acm_Total")),
        ])
        inserted += 1

    print(f"  airport_monthly: {inserted} rows inserted")

    # Show summary
    summary = con.execute("""
        SELECT airport, count(*) as months, sum(pax_total) as total_pax
        FROM airport_monthly GROUP BY airport ORDER BY total_pax DESC
    """).fetchall()
    for row in summary:
        pax = f"{row[2]:,}" if row[2] else "—"
        print(f"    {row[0]:<12} {row[1]:>3} months  {pax:>14} passengers")


def ingest_domestic_routes(con: duckdb.DuckDBPyConnection) -> None:
    """Download domestic city-pair routes CSV, filter, and load into domestic_routes."""
    rows = download_csv("routes")
    save_csv_locally("routes", rows)

    con.execute("DELETE FROM domestic_routes")

    inserted = 0
    for r in rows:
        city1 = r["City1"].strip()
        city2 = r["City2"].strip()
        year = safe_int(r.get("Year"))
        month_num = safe_int(r.get("Month_num"))

        if year is None or year < MIN_YEAR:
            continue
        # Keep only routes where at least one end is a capital city
        if city1.upper() not in AIRPORTS and city2.upper() not in AIRPORTS:
            continue

        con.execute("""
            INSERT INTO domestic_routes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            city1.upper(), city2.upper(), year, month_num,
            safe_int(r.get("Passenger_Trips")),
            safe_int(r.get("Aircraft_Trips")),
            safe_float(r.get("Passenger_Load_Factor")),
            safe_int(r.get("Distance_GC_(km)")),
            safe_int(r.get("RPKs")),
            safe_int(r.get("ASKs")),
            safe_int(r.get("Seats")),
        ])
        inserted += 1

    print(f"  domestic_routes: {inserted} rows inserted")

    # Show top routes by passengers
    top = con.execute("""
        SELECT city1, city2, sum(passenger_trips) as total
        FROM domestic_routes GROUP BY city1, city2
        ORDER BY total DESC LIMIT 10
    """).fetchall()
    for row in top:
        total = f"{row[2]:,}" if row[2] else "—"
        print(f"    {row[0]:<12} → {row[1]:<12} {total:>12} pax")


def ingest_aviation_otp(con: duckdb.DuckDBPyConnection) -> None:
    """Download OTP CSV, filter to All Airlines + 2024+ + capital cities, load."""
    rows = download_csv("otp")
    save_csv_locally("otp", rows)

    con.execute("DELETE FROM aviation_otp")

    inserted = 0
    for r in rows:
        airline = r.get("Airline", "").strip()
        year = safe_int(r.get("Year"))
        month_num = safe_int(r.get("Month_Num"))

        # All Airlines aggregates only
        if airline != "All Airlines":
            continue
        if year is None or year < MIN_YEAR:
            continue

        dep = r.get("Departing_Port", "").strip()
        arr = r.get("Arriving_Port", "").strip()

        # Keep routes where at least one end is a capital city
        # Port names in OTP: "Adelaide", "Melbourne", "Sydney", etc.
        dep_upper = dep.upper()
        arr_upper = arr.upper()
        if dep_upper not in AIRPORTS and arr_upper not in AIRPORTS:
            continue

        route = r.get("Route", "").strip()

        con.execute("""
            INSERT INTO aviation_otp VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            route, dep, arr, year, month_num,
            safe_int(r.get("Sectors_Scheduled")),
            safe_int(r.get("Sectors_Flown")),
            safe_int(r.get("Cancellations")),
            safe_int(r.get("Departures_On_Time")),
            safe_int(r.get("Arrivals_On_Time")),
            safe_int(r.get("Departures_Delayed")),
            safe_int(r.get("Arrivals_Delayed")),
        ])
        inserted += 1

    print(f"  aviation_otp: {inserted} rows inserted")

    # Show worst routes by cancellation rate
    worst = con.execute("""
        SELECT route, sum(cancellations) as total_cancel,
               sum(sectors_scheduled) as total_sched,
               round(sum(cancellations) * 100.0 / nullif(sum(sectors_scheduled), 0), 1) as cancel_pct
        FROM aviation_otp
        GROUP BY route
        HAVING sum(sectors_scheduled) > 100
        ORDER BY cancel_pct DESC LIMIT 5
    """).fetchall()
    if worst:
        print("  Highest cancellation rates:")
        for row in worst:
            print(f"    {row[0]:<30} {row[3]}% ({row[1]}/{row[2]})")


def main():
    print(f"AMIP Aviation Data Ingestion")
    print(f"  DB: {DB_PATH}")
    print(f"  Filter: {MIN_YEAR}+ | {', '.join(sorted(AIRPORTS))}")
    print()

    con = duckdb.connect(str(DB_PATH))

    print("[1/4] Creating aviation tables...")
    create_aviation_tables(con)

    print("[2/4] Airport monthly (passengers + aircraft)...")
    ingest_airport_monthly(con)

    print("[3/4] Domestic routes...")
    ingest_domestic_routes(con)

    print("[4/4] On-time performance...")
    ingest_aviation_otp(con)

    # Checkpoint to flush WAL
    print()
    print("Checkpointing...")
    con.execute("CHECKPOINT")
    con.close()

    # Final row counts
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for table in ["airport_monthly", "domestic_routes", "aviation_otp"]:
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rows")
    con.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
