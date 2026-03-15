"""
Ingest NSW station reference data into the AMIP stations table.

Source: TfNSW Road Traffic Counts Station Reference (CSV)
Target: stations table (Sydney permanent stations only for V1)

Loads from bulk CSV for initial build. The same transform logic
can later be driven by the TfNSW CKAN DataStore API for incremental updates.

Usage:
    python scripts/ingest_nsw_stations.py
"""

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
RAW_CSV = PROJECT_ROOT / "road_traffic_counts_station_reference.csv"


# Road hierarchy mapping: TfNSW categories → normalised road_type
ROAD_TYPE_MAP = {
    'Motorway': 'freeway',
    'Primary Road': 'arterial',
    'Arterial Road': 'arterial',
    'Sub-Arterial Road': 'arterial',
    'Distributor Road': 'collector',
    'Local Road': 'local',
}


def transform_nsw_stations(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """
    Read the TfNSW station reference CSV and insert Sydney permanent
    stations into the stations table. Returns row count inserted.

    Transform logic is source-agnostic — works on any DataFrame/table
    with the same columns. When switching to API, replace the CSV read
    with an API fetch and feed the same query.
    """
    # Load raw CSV into a temp view
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_nsw_stations AS
        SELECT * FROM read_csv_auto('{csv_path}')
    """)

    # Build the road_type CASE expression from our mapping
    case_clauses = "\n".join(
        f"            WHEN road_functional_hierarchy = '{k}' THEN '{v}'"
        for k, v in ROAD_TYPE_MAP.items()
    )

    # Insert Sydney permanent stations with normalised fields
    result = con.execute(f"""
        INSERT OR REPLACE INTO stations
        SELECT
            'NSW_' || CAST(station_key AS VARCHAR)  AS station_id,
            'NSW'                                    AS state,
            'Sydney'                                 AS city,
            CAST(station_key AS VARCHAR)             AS source_id,
            'tfnsw_permanent'                        AS source_system,
            road_name,
            suburb,
            wgs84_latitude                           AS latitude,
            wgs84_longitude                          AS longitude,
            CASE direction_seq
                WHEN 1 THEN 'N' WHEN 3 THEN 'S'
                WHEN 5 THEN 'E' WHEN 7 THEN 'W'
                WHEN 9 THEN 'both' WHEN 10 THEN 'both'
                ELSE CAST(direction_seq AS VARCHAR)
            END                                      AS direction,
            CASE
{case_clauses}
                ELSE 'other'
            END                                      AS road_type,
            CAST(quality_rating AS VARCHAR)           AS quality_rating
        FROM raw_nsw_stations
        WHERE rms_region = 'Sydney'
          AND permanent_station = 1
    """)

    count = con.execute("SELECT count(*) FROM stations WHERE state = 'NSW'").fetchone()[0]
    return count


if __name__ == "__main__":
    if not RAW_CSV.exists():
        print(f"ERROR: Station reference CSV not found at {RAW_CSV}")
        raise SystemExit(1)

    con = duckdb.connect(str(DB_PATH))
    count = transform_nsw_stations(con, RAW_CSV)
    print(f"NSW stations loaded: {count} Sydney permanent stations")

    # Quick verification
    sample = con.execute("""
        SELECT station_id, road_name, suburb, road_type, latitude, longitude
        FROM stations WHERE state = 'NSW'
        ORDER BY road_type, road_name
        LIMIT 10
    """).fetchall()
    print(f"\nSample:")
    for r in sample:
        print(f"  {r[0]:15s}  {r[1]:30s}  {r[2]:20s}  {r[3]:10s}  ({r[4]:.4f}, {r[5]:.4f})")

    con.close()
