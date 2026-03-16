"""
Ingest VIC TIRTL Traffic Counts and Vehicle Classification data.

Tables created:
  - tirtl_sites:       Site reference (407 locations with lat/lon)
  - tirtl_counts:      15-min aggregated counts by site, heading, vehicle class
                        (speed bins summed to total volume + weighted avg speed)

The raw data has one row per 15-min × site × heading × vehicle_class × speed_bin.
We aggregate to per 15-min × site × heading × vehicle_class with total volume
and estimated average speed (midpoint-weighted).

Usage:
  python scripts/ingest_tirtl.py
"""

from pathlib import Path
import duckdb
import glob

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
DATA_DIR = PROJECT_ROOT / "data_vic_new"

# Austroads vehicle classification lookup
VEHICLE_CLASSES = {
    0: 'Unknown',
    1: 'Car/Light vehicle',
    2: 'Car + trailer',
    3: 'Rigid truck (2 axle)',
    4: 'Rigid truck (3 axle)',
    5: 'Rigid truck (4+ axle)',
    6: 'Articulated (3-4 axle)',
    7: 'Articulated (5 axle)',
    8: 'Articulated (6 axle)',
    9: 'Articulated (7+ axle)',
    10: 'B-double',
    11: 'Road train',
    13: 'Bus (2 axle)',
    14: 'Bus (3 axle)',
}


def create_tables(con):
    """Create TIRTL tables."""

    con.execute("""
        CREATE TABLE IF NOT EXISTS tirtl_sites (
            site_id         INTEGER PRIMARY KEY,
            site_description VARCHAR,
            latitude        DOUBLE,
            longitude       DOUBLE
        )
    """)

    # Aggregated: one row per 15-min × site × heading × vehicle_class
    # Speed bins collapsed to total volume + weighted average speed
    con.execute("""
        CREATE TABLE IF NOT EXISTS tirtl_counts (
            ts_interval     TIMESTAMP NOT NULL,
            site_id         INTEGER NOT NULL,
            heading         VARCHAR(1) NOT NULL,
            vehicle_class   TINYINT NOT NULL,
            volume          INTEGER NOT NULL,
            avg_speed_kmh   SMALLINT,
            PRIMARY KEY (ts_interval, site_id, heading, vehicle_class)
        )
    """)

    con.execute("CREATE INDEX IF NOT EXISTS idx_tirtl_ts ON tirtl_counts (ts_interval)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tirtl_site ON tirtl_counts (site_id, ts_interval)")

    print("TIRTL tables created.")


def ingest_sites(con):
    """Load TIRTL site reference data."""
    f = DATA_DIR / "tirtl_sites.csv"
    if not f.exists():
        print(f"  SKIP: {f.name} not found")
        return

    con.execute("DELETE FROM tirtl_sites")
    con.execute(f"""
        INSERT INTO tirtl_sites
        SELECT site::INTEGER, site_description, latitude::DOUBLE, longitude::DOUBLE
        FROM read_csv_auto('{f}')
    """)
    count = con.execute("SELECT count(*) FROM tirtl_sites").fetchone()[0]
    print(f"  tirtl_sites: {count} sites loaded")


def parse_speed_midpoint(speed_bin):
    """Extract the midpoint speed from a bin label like '80km/hr to < 85km/hr'."""
    if not speed_bin or speed_bin == 'speed_bin':
        return None
    s = speed_bin.strip()
    if s.endswith('+'):
        # e.g. "150km/hr +" — use 152.5 as estimate
        val = s.replace('km/hr', '').replace('+', '').strip()
        return int(val) + 2
    parts = s.split(' to < ')
    if len(parts) == 2:
        low = int(parts[0].replace('km/hr', '').strip())
        return low + 2  # midpoint of 5km/h bin
    return None


def ingest_counts(con):
    """
    Load TIRTL daily CSVs, aggregate speed bins to per-interval totals.

    Raw: one row per 15-min × site × heading × vehicle_class × speed_bin
    Output: one row per 15-min × site × heading × vehicle_class
            with total volume and volume-weighted avg speed.
    """
    csv_dir = DATA_DIR / "tirtl_data"
    files = sorted(csv_dir.glob("TIRTLDATA_*.csv"))
    if not files:
        print("  SKIP: No TIRTL data files found")
        return

    print(f"  Found {len(files)} daily files to process")
    total_inserted = 0

    for f in files:
        date_str = f.stem.replace("TIRTLDATA_", "")
        print(f"    Processing {f.name}...", flush=True)

        con.execute(f"""
            INSERT OR IGNORE INTO tirtl_counts
            SELECT
                (date::DATE || ' ' || time_bin)::TIMESTAMP as ts_interval,
                site::INTEGER as site_id,
                heading,
                vehicle_class::TINYINT,
                SUM(volume::INTEGER) as volume,
                -- Weighted average speed using bin midpoints
                CASE WHEN SUM(volume::INTEGER) > 0 THEN
                    (SUM(volume::INTEGER * (
                        CASE
                            WHEN speed_bin LIKE '%+' THEN
                                CAST(REPLACE(REPLACE(speed_bin, 'km/hr', ''), ' +', '') AS INTEGER) + 2
                            WHEN speed_bin LIKE '%to%' THEN
                                CAST(REPLACE(SPLIT_PART(speed_bin, ' to', 1), 'km/hr', '') AS INTEGER) + 2
                            ELSE 0
                        END
                    )) / SUM(volume::INTEGER))::SMALLINT
                ELSE NULL END as avg_speed_kmh
            FROM read_csv_auto('{f}')
            WHERE date IS NOT NULL AND volume::INTEGER > 0
            GROUP BY 1, 2, 3, 4
        """)

        # Checkpoint after each file to prevent WAL corruption
        con.execute("CHECKPOINT")

        count = con.execute(f"""
            SELECT count(*) FROM tirtl_counts
            WHERE ts_interval::DATE = '{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}'
        """).fetchone()[0]
        print(f"      -> {count:,d} rows", flush=True)
        total_inserted += count

    con.execute("FORCE CHECKPOINT")
    print(f"  tirtl_counts: {total_inserted:,d} total rows loaded")


def verify(con):
    """Print summary stats."""
    print("\n=== TIRTL Data Summary ===")
    r = con.execute("SELECT count(*), min(ts_interval), max(ts_interval) FROM tirtl_counts").fetchone()
    print(f"Rows: {r[0]:,d}  From: {r[1]}  To: {r[2]}")

    r2 = con.execute("SELECT count(DISTINCT site_id) FROM tirtl_counts").fetchone()
    print(f"Active sites: {r2[0]}")

    # Vehicle class breakdown
    print("\nVehicle class breakdown (total volume):")
    rows = con.execute("""
        SELECT vehicle_class, SUM(volume) as total
        FROM tirtl_counts
        GROUP BY 1 ORDER BY total DESC
    """).fetchall()
    for r in rows:
        label = VEHICLE_CLASSES.get(r[0], f'Class {r[0]}')
        print(f"  Class {r[0]:>2d} ({label:<25s}): {r[1]:>12,d}")

    # Speed stats
    r3 = con.execute("""
        SELECT avg(avg_speed_kmh)::int, min(avg_speed_kmh), max(avg_speed_kmh)
        FROM tirtl_counts WHERE avg_speed_kmh > 0
    """).fetchone()
    print(f"\nSpeed: avg={r3[0]} km/h  min={r3[1]}  max={r3[2]}")


def main():
    con = duckdb.connect(str(DB_PATH))
    print(f"AMIP TIRTL Ingestion — DB: {DB_PATH}")
    create_tables(con)
    ingest_sites(con)
    ingest_counts(con)
    verify(con)
    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
