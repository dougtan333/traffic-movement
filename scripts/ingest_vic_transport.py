"""
Ingest VIC public transport patronage and vehicle registration data.

Tables created:
  - pt_patronage_monthly:  Monthly total patronage by mode (train/tram/bus/coach)
  - pt_patronage_daytype:  Monthly avg daily patronage by day type × mode × day-of-week
  - vehicle_registrations: Quarterly fleet snapshot by fuel type × postcode

Usage:
  python scripts/ingest_vic_transport.py
"""

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
DATA_DIR = PROJECT_ROOT / "data_vic_new"


def create_tables(con):
    """Create tables for PT patronage and vehicle registration data."""

    # Monthly total patronage by mode
    con.execute("""
        CREATE TABLE IF NOT EXISTS pt_patronage_monthly (
            year        SMALLINT NOT NULL,
            month       TINYINT  NOT NULL,
            month_name  VARCHAR,
            metro_train BIGINT,
            metro_tram  BIGINT,
            metro_bus   BIGINT,
            regional_train BIGINT,
            regional_coach BIGINT,
            regional_bus BIGINT,
            PRIMARY KEY (year, month)
        )
    """)

    # Monthly avg daily patronage by day type, mode, day-of-week
    con.execute("""
        CREATE TABLE IF NOT EXISTS pt_patronage_daytype (
            year        SMALLINT NOT NULL,
            month       TINYINT  NOT NULL,
            month_name  VARCHAR,
            day_of_week VARCHAR NOT NULL,
            day_type    VARCHAR NOT NULL,
            mode        VARCHAR NOT NULL,
            pax_daily   INTEGER NOT NULL,
            PRIMARY KEY (year, month, day_of_week, day_type, mode)
        )
    """)

    # Vehicle registrations — aggregated by fuel type and quarter
    # We aggregate the raw 1.1M rows down to fuel type × quarter totals
    con.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_registrations (
            quarter     VARCHAR NOT NULL,
            fuel_type   VARCHAR NOT NULL,
            vehicle_count BIGINT NOT NULL,
            PRIMARY KEY (quarter, fuel_type)
        )
    """)

    print("Tables created.")


def ingest_pt_monthly(con):
    """Load monthly PT patronage by mode."""
    f = DATA_DIR / "pt_patronage_monthly.csv"
    if not f.exists():
        print(f"  SKIP: {f.name} not found")
        return

    con.execute("DELETE FROM pt_patronage_monthly")
    con.execute(f"""
        INSERT INTO pt_patronage_monthly
        SELECT
            "Year"::SMALLINT,
            "Month"::TINYINT,
            "Month name",
            "Metropolitan train"::BIGINT,
            "Metropolitan tram"::BIGINT,
            "Metropolitan bus"::BIGINT,
            "Regional train"::BIGINT,
            "Regional coach"::BIGINT,
            "Regional bus"::BIGINT
        FROM read_csv_auto('{f}')
    """)
    count = con.execute("SELECT count(*) FROM pt_patronage_monthly").fetchone()[0]
    print(f"  pt_patronage_monthly: {count} rows loaded")


def ingest_pt_daytype(con):
    """Load monthly avg daily patronage by day type."""
    f = DATA_DIR / "pt_patronage_daytype.csv"
    if not f.exists():
        print(f"  SKIP: {f.name} not found")
        return

    con.execute("DELETE FROM pt_patronage_daytype")
    con.execute(f"""
        INSERT INTO pt_patronage_daytype
        SELECT
            "Year"::SMALLINT,
            "Month"::TINYINT,
            "Month_name",
            "Day_of_week",
            "Day_type",
            "Mode",
            "Pax_daily"::INTEGER
        FROM read_csv_auto('{f}')
    """)
    count = con.execute("SELECT count(*) FROM pt_patronage_daytype").fetchone()[0]
    print(f"  pt_patronage_daytype: {count} rows loaded")


def ingest_vehicle_registrations(con):
    """Load vehicle registrations, aggregated by fuel type per quarter."""
    f = DATA_DIR / "vehicle_registrations_q4_2025.csv"
    if not f.exists():
        print(f"  SKIP: {f.name} not found")
        return

    # Map fuel codes to readable names
    fuel_map = {
        'P': 'Petrol', 'D': 'Diesel', 'E': 'Electric',
        'M': 'Hybrid', 'G': 'LPG/Gas', 'O': 'Other',
        'S': 'Solar', 'R': 'Other',
    }

    con.execute("DELETE FROM vehicle_registrations")

    # Aggregate raw data by fuel type — the file is a single quarter snapshot
    con.execute(f"""
        INSERT INTO vehicle_registrations
        SELECT
            'Q4-2025' as quarter,
            CASE TRIM("CD_CL_FUEL_ENG")
                WHEN 'P' THEN 'Petrol'
                WHEN 'D' THEN 'Diesel'
                WHEN 'E' THEN 'Electric'
                WHEN 'M' THEN 'Hybrid'
                WHEN 'G' THEN 'LPG/Gas'
                ELSE 'Other'
            END as fuel_type,
            SUM("TOTAL1"::BIGINT) as vehicle_count
        FROM read_csv_auto('{f}')
        WHERE TRIM("CD_CL_FUEL_ENG") != ''
        GROUP BY 1, 2
    """)
    rows = con.execute("SELECT fuel_type, vehicle_count FROM vehicle_registrations ORDER BY vehicle_count DESC").fetchall()
    print(f"  vehicle_registrations: {len(rows)} fuel types loaded")
    for r in rows:
        print(f"    {r[0]:<10s} {r[1]:>10,d}")


def main():
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP Transport Data Ingestion — DB: {DB_PATH}")
    create_tables(con)
    ingest_pt_monthly(con)
    ingest_pt_daytype(con)
    ingest_vehicle_registrations(con)
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
