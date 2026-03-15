"""
Ingest NSW hourly permanent traffic counts into the AMIP hourly_counts table.

Source: TfNSW bulk CSV files (road_traffic_counts_hourly_permanent*.csv)
Target: hourly_counts table

The raw NSW format has one row per station per day with 24 hour columns
(hour_00 through hour_23). This script unpivots to one row per station
per hour, matching the unified schema.

Only stations present in the stations table (Sydney permanent) are loaded.

For incremental updates: swap the CSV glob for a TfNSW CKAN API call
filtered by date range. The unpivot transform is identical.

Usage:
    python scripts/ingest_nsw_counts.py
"""

from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
RAW_DIR = PROJECT_ROOT / "road_traffic_counts_hourly_permanent"


def transform_nsw_counts(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> int:
    """
    Read NSW hourly CSV files, unpivot hour columns to rows,
    filter to stations in the stations table, and insert into hourly_counts.

    The unpivot converts:
      station_key | date | hour_00 | hour_01 | ... | hour_23
    into:
      station_id | ts_hour | vehicle_count | state | day_of_week | hour_of_day | is_weekday

    Returns row count inserted.
    """
    # Load raw CSVs into a temp view — DuckDB glob handles all 5 files
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_nsw_counts AS
        SELECT * FROM read_csv_auto('{raw_dir}/*.csv', union_by_name=true)
    """)

    # Unpivot hour columns and join to stations for filtering + station_id mapping
    # The date column includes timezone — we strip it and treat as AEST
    con.execute("""
        INSERT OR REPLACE INTO hourly_counts
        WITH unpivoted AS (
            SELECT
                station_key,
                date,
                hr.hour_num,
                hr.vehicle_count
            FROM raw_nsw_counts
            CROSS JOIN LATERAL (VALUES
                (0, hour_00), (1, hour_01), (2, hour_02), (3, hour_03),
                (4, hour_04), (5, hour_05), (6, hour_06), (7, hour_07),
                (8, hour_08), (9, hour_09), (10, hour_10), (11, hour_11),
                (12, hour_12), (13, hour_13), (14, hour_14), (15, hour_15),
                (16, hour_16), (17, hour_17), (18, hour_18), (19, hour_19),
                (20, hour_20), (21, hour_21), (22, hour_22), (23, hour_23)
            ) AS hr(hour_num, vehicle_count)
            WHERE hr.vehicle_count IS NOT NULL
        )
        SELECT
            s.station_id,
            -- Construct timestamp: date (stripped to DATE) + hour
            CAST(CAST(u.date AS DATE) AS TIMESTAMP) + INTERVAL (u.hour_num) HOUR
                AS ts_hour,
            u.vehicle_count::INTEGER,
            'NSW'                                   AS state,
            ISODOW(CAST(u.date AS DATE))::TINYINT   AS day_of_week,
            u.hour_num::TINYINT                     AS hour_of_day,
            ISODOW(CAST(u.date AS DATE)) <= 5       AS is_weekday
        FROM unpivoted u
        INNER JOIN stations s
            ON s.source_id = CAST(u.station_key AS VARCHAR)
            AND s.state = 'NSW'
    """)

    count = con.execute("SELECT count(*) FROM hourly_counts WHERE state = 'NSW'").fetchone()[0]
    return count


if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))

    # Check stations are loaded
    nsw_stations = con.execute("SELECT count(*) FROM stations WHERE state = 'NSW'").fetchone()[0]
    if nsw_stations == 0:
        print("ERROR: No NSW stations in DB. Run ingest_nsw_stations.py first.")
        raise SystemExit(1)

    print(f"Found {nsw_stations} NSW stations. Loading hourly counts...")
    print(f"Source: {RAW_DIR}")
    print("This may take a few minutes for ~2M rows...")

    count = transform_nsw_counts(con, RAW_DIR)
    print(f"\nNSW hourly counts loaded: {count:,d} rows")

    # Verification
    stats = con.execute("""
        SELECT
            min(ts_hour) as min_ts,
            max(ts_hour) as max_ts,
            count(DISTINCT station_id) as stations,
            avg(vehicle_count)::int as avg_count
        FROM hourly_counts WHERE state = 'NSW'
    """).fetchone()
    print(f"Date range: {stats[0]} to {stats[1]}")
    print(f"Stations: {stats[2]}")
    print(f"Avg hourly count: {stats[3]}")

    con.close()
