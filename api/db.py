"""
Database connection helpers for the AMIP API.

Two databases:
  - amip.duckdb:  SCATS counts, stations, calendar, fuel, aviation, transport.
                  Written to only during daily refresh (7am AEST). Always readable.
  - speed.duckdb: speed_observations, bluetooth_routes, bluetooth_links.
                  Written to every 5 minutes by the Bluetooth poller.
                  Retry logic handles brief WAL locks during poll writes.

Each request gets its own connection (DuckDB handles this efficiently).
"""

from pathlib import Path
import time
import duckdb

_DB_DIR = Path(__file__).resolve().parent.parent / "db"
DB_PATH = _DB_DIR / "amip.duckdb"
SPEED_DB_PATH = _DB_DIR / "speed.duckdb"
ARCHIVE_DIR = _DB_DIR / "archive"


BASELINE_START = "2026-02-01"
BASELINE_END = "2026-02-28"


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a read-only connection to the main AMIP database.
    After the speed DB split, this DB is only written to during the
    daily refresh at 7am — so lock conflicts should be extremely rare.
    Retry logic kept as a safety net."""
    for attempt in range(5):
        try:
            return duckdb.connect(str(DB_PATH), read_only=True)
        except (duckdb.IOException, Exception) as e:
            if "lock" in str(e).lower() and attempt < 4:
                time.sleep(1)
            else:
                raise


def get_speed_connection() -> duckdb.DuckDBPyConnection:
    """Return a read-only connection to the speed/Bluetooth database.
    The Bluetooth poller writes here every 5 minutes, so brief WAL
    lock conflicts are expected. The API-level response cache (api/cache.py)
    covers users during these windows; retries here are a belt-and-suspenders
    fallback."""
    for attempt in range(5):
        try:
            return duckdb.connect(str(SPEED_DB_PATH), read_only=True)
        except (duckdb.IOException, Exception) as e:
            if "lock" in str(e).lower() and attempt < 4:
                time.sleep(1)
            else:
                raise


def get_metro_core_count(con: duckdb.DuckDBPyConnection) -> int:
    """Return the number of metro core stations from the permanent table.
    The table is materialized by scripts/materialize_metro_core.py and
    refreshed daily via daily_refresh.py. This replaces the old
    create_metro_core_table() which rebuilt the cohort on every request."""
    return con.execute("SELECT count(*) FROM metro_core_stations").fetchone()[0]
