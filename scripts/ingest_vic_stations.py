"""
Ingest VIC traffic signal site reference into the AMIP stations table.

Source: VicRoads Traffic Lights CSV (ArcGIS export)
Target: stations table (sites that match SCATS volume data)

Coordinates are in VicGrid94 (EPSG:3111) and are reprojected to WGS84.
Only sites that appear in the SCATS volume data are loaded.

Usage:
    python scripts/ingest_vic_stations.py
"""

from pathlib import Path
import duckdb
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
TL_CSV = PROJECT_ROOT / "Traffic_Lights.csv"
SCATS_DIR = PROJECT_ROOT / "traffic_signal_volume_data_march_2026"


# VicGrid94 (EPSG:3111) → WGS84 (EPSG:4326)
TRANSFORMER = Transformer.from_crs("EPSG:3111", "EPSG:4326", always_xy=True)


def transform_vic_stations(con: duckdb.DuckDBPyConnection, tl_csv: Path, scats_dir: Path) -> int:
    """
    Read the Traffic Lights CSV, reproject coordinates, and insert
    into stations table. Only includes sites that exist in the SCATS
    volume data (inner join on SITE_NO = NB_SCATS_SITE).

    Returns row count inserted.
    """
    # Load traffic lights reference
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_tl AS
        SELECT * FROM read_csv_auto('{tl_csv}')
    """)

    # Get distinct SCATS site IDs from volume data
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW scats_sites AS
        SELECT DISTINCT NB_SCATS_SITE AS site_no
        FROM read_csv_auto('{scats_dir}/*.csv', union_by_name=true)
    """)

    # Get matched sites with their coordinates
    matched = con.execute("""
        SELECT tl.SITE_NO, tl.SITE_NAME, tl.X, tl.Y
        FROM raw_tl tl
        INNER JOIN scats_sites s ON tl.SITE_NO = s.site_no
        WHERE tl.X != 0 AND tl.Y != 0
    """).fetchall()

    # Reproject and prepare insert data
    rows = []
    for site_no, site_name, x, y in matched:
        lon, lat = TRANSFORMER.transform(x, y)
        # Parse road names from SITE_NAME (format: "ROAD_A/ROAD_B" or "ROAD NR LANDMARK")
        parts = site_name.split('/')
        road_name = parts[0].strip() if parts else site_name
        rows.append((
            f"VIC_{site_no}",       # station_id
            'VIC',                   # state
            'Melbourne',             # city
            str(site_no),            # source_id
            'vic_scats',             # source_system
            road_name,               # road_name (first road from intersection)
            None,                    # suburb (not in traffic lights data)
            lat,                     # latitude (WGS84)
            lon,                     # longitude (WGS84)
            None,                    # direction (not available per-site)
            'signalised',            # road_type — all SCATS sites are signalised intersections
            None,                    # quality_rating
        ))

    # Bulk insert
    con.executemany("""
        INSERT OR REPLACE INTO stations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    count = con.execute("SELECT count(*) FROM stations WHERE state = 'VIC'").fetchone()[0]
    return count


if __name__ == "__main__":
    if not TL_CSV.exists():
        print(f"ERROR: Traffic Lights CSV not found at {TL_CSV}")
        raise SystemExit(1)

    con = duckdb.connect(str(DB_PATH))
    count = transform_vic_stations(con, TL_CSV, SCATS_DIR)
    print(f"VIC stations loaded: {count} SCATS-matched signal sites")

    sample = con.execute("""
        SELECT station_id, road_name, latitude, longitude
        FROM stations WHERE state = 'VIC'
        LIMIT 10
    """).fetchall()
    print(f"\nSample:")
    for r in sample:
        print(f"  {r[0]:12s}  {r[1]:40s}  ({r[2]:.5f}, {r[3]:.5f})")

    con.close()
