"""
Ingest VIC SCATS volume data into the AMIP hourly_counts table.

Source: VIC Traffic Signal Volume Data (monthly CSV ZIPs from DTP)
Target: hourly_counts table

SCATS data has 96 interval columns (V00–V95) = 96 × 15-minute intervals per day.
Each row is one detector on one site for one day.

This script:
1. Finds all traffic_signal_volume_data_* directories (excluding the zip archive)
2. Processes each month sequentially to manage memory
3. Aggregates 15-min intervals to hourly (sum of 4 consecutive intervals)
4. Aggregates across detectors per site (sum all active detectors)
5. Filters to sites present in the stations table
6. Inserts into hourly_counts with unified schema

For incremental updates: download the latest monthly ZIP, extract, and re-run.
Only new data (by primary key) will be inserted; existing rows are replaced.

Usage:
    python scripts/ingest_vic_counts.py
"""

from pathlib import Path
import duckdb
import glob
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"


def find_scats_dirs(project_root: Path) -> list[Path]:
    """
    Find all extracted SCATS monthly data directories.
    Excludes the 2024 zip archive folder (contains .zip files, not CSVs).
    Returns sorted list of paths.
    """
    pattern = str(project_root / "traffic_signal_volume_data_*")
    dirs = []
    for d in sorted(glob.glob(pattern)):
        p = Path(d)
        if not p.is_dir():
            continue
        # Skip the zip archive folder (contains .zip files not .csv)
        csvs = list(p.glob("VSDATA_*.csv"))
        if csvs:
            dirs.append(p)
    return dirs



def transform_vic_month(con: duckdb.DuckDBPyConnection, scats_dir: Path) -> int:
    """
    Process one month of SCATS data: aggregate 15-min to hourly,
    sum across detectors per site, insert into hourly_counts.

    Returns row count inserted for this month.
    """
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW raw_scats AS
        SELECT * FROM read_csv_auto('{scats_dir}/*.csv', union_by_name=true)
    """)

    # Build hourly aggregation: each hour = sum of 4 consecutive 15-min intervals
    hour_exprs = []
    for h in range(24):
        v_start = h * 4
        cols = " + ".join(f"COALESCE(V{v_start+i:02d}, 0)" for i in range(4))
        hour_exprs.append(f"SUM({cols}) AS h{h:02d}")

    hour_select = ",\n            ".join(hour_exprs)

    # Aggregate to hourly per site per day
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE hourly_by_site AS
        SELECT
            NB_SCATS_SITE AS site_no,
            QT_INTERVAL_COUNT AS obs_date,
            {hour_select}
        FROM raw_scats
        GROUP BY NB_SCATS_SITE, QT_INTERVAL_COUNT
    """)

    # Unpivot hours and join to stations
    values_list = ", ".join(f"({h}, h{h:02d})" for h in range(24))

    result = con.execute(f"""
        INSERT OR REPLACE INTO hourly_counts
        SELECT
            s.station_id,
            CAST(obs_date AS TIMESTAMP) + INTERVAL (hr.hour_num) HOUR
                AS ts_hour,
            hr.vehicle_count::INTEGER,
            'VIC'                                    AS state,
            ISODOW(CAST(obs_date AS DATE))::TINYINT  AS day_of_week,
            hr.hour_num::TINYINT                     AS hour_of_day,
            ISODOW(CAST(obs_date AS DATE)) <= 5      AS is_weekday
        FROM hourly_by_site h
        CROSS JOIN LATERAL (VALUES {values_list}) AS hr(hour_num, vehicle_count)
        INNER JOIN stations s
            ON s.source_id = CAST(h.site_no AS VARCHAR)
            AND s.state = 'VIC'
        WHERE hr.vehicle_count > 0
    """)

    # Count rows just inserted (by querying the date range of this month's data)
    date_range = con.execute("""
        SELECT min(obs_date), max(obs_date) FROM hourly_by_site
    """).fetchone()
    if date_range[0] is None:
        return 0
    count = con.execute(f"""
        SELECT count(*) FROM hourly_counts
        WHERE state = 'VIC'
          AND CAST(ts_hour AS DATE) BETWEEN '{date_range[0]}' AND '{date_range[1]}'
    """).fetchone()[0]
    return count



if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH))

    vic_stations = con.execute("SELECT count(*) FROM stations WHERE state = 'VIC'").fetchone()[0]
    if vic_stations == 0:
        print("ERROR: No VIC stations in DB. Run ingest_vic_stations.py first.")
        raise SystemExit(1)

    # Clear existing VIC counts for clean reload
    con.execute("DELETE FROM hourly_counts WHERE state = 'VIC'")
    print(f"Cleared existing VIC counts. Found {vic_stations} VIC stations.")

    dirs = find_scats_dirs(PROJECT_ROOT)
    print(f"Found {len(dirs)} SCATS data directories to process.\n")

    total = 0
    for i, d in enumerate(dirs, 1):
        csv_count = len(list(d.glob("VSDATA_*.csv")))
        print(f"  [{i}/{len(dirs)}] {d.name} ({csv_count} days)...", end=" ", flush=True)
        month_count = transform_vic_month(con, d)
        total += month_count
        print(f"{month_count:,d} rows")

    print(f"\nTotal VIC hourly counts loaded: {total:,d} rows")

    # Final verification
    stats = con.execute("""
        SELECT
            min(ts_hour) as min_ts,
            max(ts_hour) as max_ts,
            count(DISTINCT station_id) as stations,
            count(*) as total_rows,
            avg(vehicle_count)::int as avg_count
        FROM hourly_counts WHERE state = 'VIC'
    """).fetchone()
    print(f"\nDate range: {stats[0]} to {stats[1]}")
    print(f"Stations: {stats[2]}")
    print(f"Total rows: {stats[3]:,d}")
    print(f"Avg hourly count: {stats[4]}")

    con.close()
