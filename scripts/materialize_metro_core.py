"""
Materialize the metro core station cohort as a permanent DuckDB table.

Metro core = stations with P75+ average weekday daily volume during
the Feb 2026 baseline period. This replaces the per-request temp table
approach that was scanning 73M rows on every API call.

Run manually:   python scripts/materialize_metro_core.py
Run via daily:   called by daily_refresh.py as first job

Pattern: connect/disconnect per operation (DuckDB write lock safety).
"""

import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "amip.duckdb"
BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"


def materialize():
    """Create/replace the permanent metro_core_stations table."""
    con = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        con.execute(f"""
            CREATE OR REPLACE TABLE metro_core_stations AS
            SELECT station_id, avg_daily FROM (
                SELECT station_id,
                       sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE)) as avg_daily
                FROM hourly_counts h
                WHERE h.state = 'VIC' AND ISODOW(CAST(ts_hour AS DATE)) <= 5
                  AND CAST(ts_hour AS DATE) BETWEEN '{BASELINE_START}' AND '{BASELINE_END}'
                GROUP BY station_id
            )
            WHERE avg_daily >= (
                SELECT percentile_cont(0.75) WITHIN GROUP (ORDER BY avg_daily) FROM (
                    SELECT station_id,
                           sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE)) as avg_daily
                    FROM hourly_counts h
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
    materialize()
