"""
Database connection helper for the AMIP API.

Returns a read-only DuckDB connection to amip.duckdb.
Each request gets its own connection (DuckDB handles this efficiently).
"""

from pathlib import Path
import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "amip.duckdb"


BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a read-only connection to the AMIP database."""
    return duckdb.connect(str(DB_PATH), read_only=True)


def create_metro_core_table(con: duckdb.DuckDBPyConnection) -> int:
    """Create a temp table of metro core stations (P75+ avg daily volume
    from the Feb 2026 baseline period). Returns the station count."""
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE metro_core_stations AS
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
    return con.execute("SELECT count(*) FROM metro_core_stations").fetchone()[0]
