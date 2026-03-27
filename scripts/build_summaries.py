"""
Build pre-aggregated summary tables from Parquet archives.

Creates two summary tables that replace 73M-row scans with ~790K rows:

1. daily_station_summary (metro core) — ~770K rows
   One row per station per day. Used by: weekly-trend, daily-counts,
   month-on-month, school-holiday, peak-days, event-impact, weekday-drift, monitor.

2. hourly_city_summary (all stations) — ~19K rows
   One row per hour per day, averaged across all stations. Used by:
   hourly-profile, heatmap, day-of-week.

Reads from Parquet archives in db/archive/ (hourly_counts table was
dropped in DEC-032).

Usage:
  python scripts/build_summaries.py           # full rebuild
  python scripts/build_summaries.py --append  # append new days only

Pattern: connect/disconnect per operation (DuckDB write lock safety).
"""

import argparse
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "amip.duckdb"
ARCHIVE_DIR = Path(__file__).resolve().parent.parent / "db" / "archive"


def _parquet_glob():
    """Return glob pattern for all hourly_counts Parquet archives."""
    pattern = str(ARCHIVE_DIR / "hourly_counts_*.parquet")
    return pattern


def build_daily_station(con, append=False):
    """Per-station daily totals for metro core stations."""
    parquet = _parquet_glob()

    if append:
        latest = con.execute("""
            SELECT max(day) FROM daily_station_summary
        """).fetchone()[0]
        if latest:
            date_filter = f"AND CAST(h.ts_hour AS DATE) > '{latest}'"
            print(f"  Appending days after {latest}")
        else:
            date_filter = ""
            print("  Table empty, doing full build")
    else:
        con.execute("DROP TABLE IF EXISTS daily_station_summary")
        date_filter = ""
        print("  Full rebuild")

    con.execute(f"""
        {'CREATE TABLE daily_station_summary AS' if not append else 'INSERT INTO daily_station_summary'}
        SELECT h.station_id,
               CAST(h.ts_hour AS DATE) as day,
               SUM(h.vehicle_count)::INT as daily_total,
               SUM(CASE WHEN h.hour_of_day BETWEEN 7 AND 17 THEN h.vehicle_count ELSE 0 END)::INT as biz_hours_total,
               ISODOW(CAST(h.ts_hour AS DATE)) as day_of_week,
               CASE WHEN ISODOW(CAST(h.ts_hour AS DATE)) <= 5 THEN true ELSE false END as is_weekday,
               EXTRACT(YEAR FROM CAST(h.ts_hour AS DATE))::INT as year,
               EXTRACT(MONTH FROM CAST(h.ts_hour AS DATE))::INT as month
        FROM read_parquet('{parquet}') h
        INNER JOIN metro_core_stations m ON h.station_id = m.station_id
        WHERE h.state = 'VIC' {date_filter}
        GROUP BY h.station_id, CAST(h.ts_hour AS DATE)
    """)

    count = con.execute("SELECT count(*) FROM daily_station_summary").fetchone()[0]
    days = con.execute("SELECT count(DISTINCT day) FROM daily_station_summary").fetchone()[0]
    print(f"  daily_station_summary: {count:,} rows ({days} days)")
    return count


def build_hourly_city(con, append=False):
    """Hourly city-level averages across ALL stations."""
    parquet = _parquet_glob()

    if append:
        latest = con.execute("""
            SELECT max(day) FROM hourly_city_summary
        """).fetchone()[0]
        if latest:
            date_filter = f"AND CAST(h.ts_hour AS DATE) > '{latest}'"
            print(f"  Appending days after {latest}")
        else:
            date_filter = ""
            print("  Table empty, doing full build")
    else:
        con.execute("DROP TABLE IF EXISTS hourly_city_summary")
        date_filter = ""
        print("  Full rebuild")

    con.execute(f"""
        {'CREATE TABLE hourly_city_summary AS' if not append else 'INSERT INTO hourly_city_summary'}
        SELECT CAST(h.ts_hour AS DATE) as day,
               h.hour_of_day,
               AVG(h.vehicle_count)::INT as avg_count,
               SUM(h.vehicle_count)::BIGINT as total_count,
               COUNT(DISTINCT h.station_id)::INT as stations,
               ISODOW(CAST(h.ts_hour AS DATE)) as day_of_week,
               CASE WHEN ISODOW(CAST(h.ts_hour AS DATE)) <= 5 THEN true ELSE false END as is_weekday,
               EXTRACT(YEAR FROM CAST(h.ts_hour AS DATE))::INT as year
        FROM read_parquet('{parquet}') h
        WHERE h.state = 'VIC' {date_filter}
        GROUP BY CAST(h.ts_hour AS DATE), h.hour_of_day
    """)

    count = con.execute("SELECT count(*) FROM hourly_city_summary").fetchone()[0]
    days = con.execute("SELECT count(DISTINCT day) FROM hourly_city_summary").fetchone()[0]
    print(f"  hourly_city_summary: {count:,} rows ({days} days)")
    return count


def build_all(append=False):
    """Build both summary tables."""
    con = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        mode = "append" if append else "full rebuild"
        print(f"Building summary tables ({mode})...")

        print("\n1. daily_station_summary (metro core):")
        build_daily_station(con, append=append)

        print("\n2. hourly_city_summary (all stations):")
        build_hourly_city(con, append=append)

        con.execute("CHECKPOINT")
        print("\nCheckpoint complete.")

        # Show DB size
        import os
        size_mb = os.path.getsize(str(DB_PATH)) / (1024 * 1024)
        print(f"DB size: {size_mb:.0f} MB")
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build AMIP summary tables")
    parser.add_argument("--append", action="store_true",
                        help="Append new days only (default: full rebuild)")
    args = parser.parse_args()
    build_all(append=args.append)
