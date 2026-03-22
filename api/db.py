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


def get_metro_core_count(con: duckdb.DuckDBPyConnection) -> int:
    """Return the number of metro core stations from the permanent table.
    The table is materialized by scripts/materialize_metro_core.py and
    refreshed daily via daily_refresh.py. This replaces the old
    create_metro_core_table() which rebuilt the cohort on every request."""
    return con.execute("SELECT count(*) FROM metro_core_stations").fetchone()[0]
