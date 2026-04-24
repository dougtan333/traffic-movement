"""
Materialize the metro core station cohort as a permanent DuckDB table.

Metro core = stations with P75+ average weekday daily volume during
the Feb 2026 baseline period. This replaces the per-request temp table
approach that was scanning 73M rows on every API call.

Reads from the Parquet archive (hourly_counts table was dropped after
summary tables were built — DEC-032).

The Feb 2026 cohort is a FROZEN baseline (DEC-040). This script is a
no-op if metro_core_stations already exists. Use --force only for an
intentional rebaseline (e.g. annual review). Rebuilding silently would
change which stations are included and break trend continuity.

Run manually (first time or forced rebaseline):
    python scripts/materialize_metro_core.py
    python scripts/materialize_metro_core.py --force

Run via daily_refresh.py: no-op after first materialisation.

Pattern: connect/disconnect per operation (DuckDB write lock safety).
"""

import argparse
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "amip.duckdb"
ARCHIVE_DIR = Path(__file__).resolve().parent.parent / "db" / "archive"
BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"
BASELINE_PARQUET = ARCHIVE_DIR / "hourly_counts_2026.parquet"


def materialize(force: bool = False):
    """Create the permanent metro_core_stations table.

    Skips silently if the table already exists, unless force=True.
    The cohort is frozen at Feb 2026 — never rebuilt automatically.
    """
    con = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        # Skip if already materialized — cohort is frozen at Feb 2026 (DEC-040)
        if not force:
            exists = con.execute("""
                SELECT count(*) FROM information_schema.tables
                WHERE table_name = 'metro_core_stations'
            """).fetchone()[0]
            if exists:
                count = con.execute("SELECT count(*) FROM metro_core_stations").fetchone()[0]
                print(f"metro_core_stations already exists ({count} stations) — skipping. Use --force to rebuild.")
                return count

        if not BASELINE_PARQUET.exists():
            print(f"ERROR: Parquet archive not found: {BASELINE_PARQUET}")
            return 0

        con.execute(f"""
            CREATE OR REPLACE TABLE metro_core_stations AS
            SELECT station_id, avg_daily FROM (
                SELECT station_id,
                       sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE)) as avg_daily
                FROM read_parquet('{BASELINE_PARQUET}') h
                WHERE h.state = 'VIC' AND ISODOW(CAST(ts_hour AS DATE)) <= 5
                  AND CAST(ts_hour AS DATE) BETWEEN '{BASELINE_START}' AND '{BASELINE_END}'
                GROUP BY station_id
            )
            WHERE avg_daily >= (
                SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY avg_daily) FROM (
                    SELECT station_id,
                           sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE)) as avg_daily
                    FROM read_parquet('{BASELINE_PARQUET}') h
                    WHERE h.state = 'VIC' AND ISODOW(CAST(ts_hour AS DATE)) <= 5
                      AND CAST(ts_hour AS DATE) BETWEEN '{BASELINE_START}' AND '{BASELINE_END}'
                    GROUP BY station_id
                )
            )
        """)
        count = con.execute("SELECT count(*) FROM metro_core_stations").fetchone()[0]
        con.execute("CHECKPOINT")
        print(f"metro_core_stations materialized: {count} stations (P75+ from {BASELINE_START} to {BASELINE_END})")
    finally:
        con.close()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Materialize metro core station cohort")
    parser.add_argument("--force", action="store_true",
                        help="Rebuild even if table already exists (intentional rebaseline only)")
    args = parser.parse_args()
    materialize(force=args.force)
