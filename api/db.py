"""
Database connection helper for the AMIP API.

Returns a read-only DuckDB connection to amip.duckdb.
Each request gets its own connection (DuckDB handles this efficiently).
"""

from pathlib import Path
import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "amip.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a read-only connection to the AMIP database."""
    return duckdb.connect(str(DB_PATH), read_only=True)
