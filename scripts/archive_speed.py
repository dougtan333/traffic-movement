"""
archive_speed.py — Export speed_observations to Parquet archive

Exports the current speed_observations table to a date-partitioned Parquet
file in db/archive/speed/. Each run creates a snapshot of all data not yet
archived, appending to the archive.

Usage:
  python scripts/archive_speed.py              # archive new data
  python scripts/archive_speed.py --full       # full re-export

The poller must be stopped before running --full (writes to DB).
Safe to run alongside the poller for incremental archives (read-only).
"""

import argparse
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
ARCHIVE_DIR = PROJECT_ROOT / "db" / "archive" / "speed"
AEST = timezone(timedelta(hours=10))


def archive_full(con):
    """Full export of all speed_observations to a single Parquet file."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(AEST).strftime("%Y%m%d_%H%M")
    out_path = ARCHIVE_DIR / f"speed_observations_{ts}.parquet"

    row_count = con.execute("SELECT COUNT(*) FROM speed_observations").fetchone()[0]
    if row_count == 0:
        print("No speed data to archive.")
        return

    print(f"Exporting {row_count:,} rows to {out_path}...")
    con.execute(f"""
        COPY (SELECT * FROM speed_observations ORDER BY ts_interval, route_id)
        TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Archive complete: {out_path.name} ({size_mb:.1f} MB, {row_count:,} rows)")


def archive_incremental(con):
    """
    Export only data newer than the latest archived date.
    Reads the archive dir to find the most recent file, then exports
    everything after that point.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Find latest archived timestamp by checking existing parquet files
    existing = sorted(ARCHIVE_DIR.glob("speed_*.parquet"))
    if existing:
        # Read max ts_interval from the most recent archive
        latest_file = existing[-1]
        try:
            max_ts = con.execute(f"""
                SELECT MAX(ts_interval) FROM read_parquet('{latest_file}')
            """).fetchone()[0]
            print(f"Latest archived timestamp: {max_ts}")
        except Exception as e:
            print(f"WARNING: Could not read {latest_file}: {e}")
            max_ts = None
    else:
        max_ts = None
        print("No existing archives — exporting all data.")

    # Build query for new data
    if max_ts:
        where = f"WHERE ts_interval > '{max_ts}'"
    else:
        where = ""

    row_count = con.execute(
        f"SELECT COUNT(*) FROM speed_observations {where}"
    ).fetchone()[0]

    if row_count == 0:
        print("No new data to archive.")
        return

    ts = datetime.now(AEST).strftime("%Y%m%d_%H%M")
    out_path = ARCHIVE_DIR / f"speed_incremental_{ts}.parquet"

    print(f"Exporting {row_count:,} new rows to {out_path}...")
    con.execute(f"""
        COPY (SELECT * FROM speed_observations {where} ORDER BY ts_interval, route_id)
        TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Incremental archive: {out_path.name} ({size_mb:.1f} MB, {row_count:,} rows)")


def main():
    parser = argparse.ArgumentParser(description="Archive speed data to Parquet")
    parser.add_argument("--full", action="store_true", help="Full re-export (stop poller first)")
    args = parser.parse_args()

    print(f"AMIP Speed Archiver — DB: {DB_PATH}")
    print(f"Archive dir: {ARCHIVE_DIR}")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        if args.full:
            archive_full(con)
        else:
            archive_incremental(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
