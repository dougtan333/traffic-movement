"""
migrate_speed_db.py — Extract speed tables from amip.duckdb into speed.duckdb

Moves bluetooth_routes, bluetooth_links, and speed_observations out of the
main database into a dedicated speed.duckdb. This separates the Bluetooth
poller's write path from the main API read path, eliminating WAL lock
conflicts that caused intermittent frontend downtime.

Run ONCE after stopping the Bluetooth poller:
  sudo systemctl stop amip-bluetooth
  python scripts/migrate_speed_db.py
  sudo systemctl restart amip-api
  sudo systemctl start amip-bluetooth

After verifying speed.duckdb works correctly, drop the old tables from
amip.duckdb manually (script prints instructions).

Safe to re-run — skips tables that already exist in speed.duckdb.
"""

import sys
from pathlib import Path
import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AMIP_DB = PROJECT_ROOT / "db" / "amip.duckdb"
SPEED_DB = PROJECT_ROOT / "db" / "speed.duckdb"

# Tables to migrate — order matters (routes/links before observations for FK)
SPEED_TABLES = ["bluetooth_routes", "bluetooth_links", "speed_observations"]


def get_row_count(con, table):
    """Return row count for a table, or -1 if it doesn't exist."""
    try:
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1


def table_exists(con, table):
    """Check if a table exists in the connected database."""
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name='main'"
        ).fetchall()]
        return table in tables
    except Exception:
        return False


def migrate():
    if not AMIP_DB.exists():
        print(f"ERROR: Source database not found: {AMIP_DB}")
        sys.exit(1)

    print(f"Source:  {AMIP_DB}")
    print(f"Target:  {SPEED_DB}")
    print()

    # Open speed.duckdb read-write (creates if needed), attach amip as read-only
    speed_con = duckdb.connect(str(SPEED_DB))
    speed_con.execute(f"ATTACH '{AMIP_DB}' AS amip (READ_ONLY)")

    # Check what exists in source
    amip_tables = [r[0] for r in speed_con.execute(
        "SELECT table_name FROM amip.duckdb_tables() WHERE schema_name='main'"
    ).fetchall()]

    migrated = 0
    for table in SPEED_TABLES:
        if table not in amip_tables:
            print(f"  SKIP {table} — not found in amip.duckdb")
            continue

        if table_exists(speed_con, table):
            existing = get_row_count(speed_con, table)
            print(f"  SKIP {table} — already exists in speed.duckdb ({existing:,} rows)")
            continue

        source_count = speed_con.execute(f"SELECT count(*) FROM amip.main.{table}").fetchone()[0]
        print(f"  Migrating {table} ({source_count:,} rows)...", end=" ", flush=True)

        # CREATE TABLE AS SELECT preserves column types
        speed_con.execute(f"CREATE TABLE {table} AS SELECT * FROM amip.main.{table}")

        target_count = get_row_count(speed_con, table)
        if target_count == source_count:
            print(f"OK ({target_count:,} rows)")
            migrated += 1
        else:
            print(f"WARNING: count mismatch (source={source_count:,}, target={target_count:,})")

    speed_con.execute("CHECKPOINT")
    speed_con.execute("DETACH amip")
    speed_con.close()

    # Restore primary keys and indexes (CREATE TABLE AS doesn't carry them)
    print()
    print("Restoring indexes...")
    speed_con = duckdb.connect(str(SPEED_DB))

    # bluetooth_routes PK
    try:
        speed_con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_bt_routes_pk
            ON bluetooth_routes (route_id)
        """)
        print("  bluetooth_routes: unique index on route_id")
    except Exception as e:
        print(f"  bluetooth_routes index: {e}")

    # speed_observations composite PK + ts index
    try:
        speed_con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_so_pk
            ON speed_observations (route_id, ts_interval)
        """)
        speed_con.execute("""
            CREATE INDEX IF NOT EXISTS idx_so_ts
            ON speed_observations (ts_interval)
        """)
        print("  speed_observations: unique index on (route_id, ts_interval) + ts_interval index")
    except Exception as e:
        print(f"  speed_observations index: {e}")

    speed_con.execute("CHECKPOINT")
    speed_con.close()

    # Final verification
    print()
    speed_con = duckdb.connect(str(SPEED_DB), read_only=True)
    print("Verification (speed.duckdb):")
    for table in SPEED_TABLES:
        count = get_row_count(speed_con, table)
        if count >= 0:
            print(f"  {table}: {count:,} rows")
        else:
            print(f"  {table}: NOT FOUND")
    speed_con.close()

    size_mb = SPEED_DB.stat().st_size / (1024 * 1024)
    print(f"\nspeed.duckdb size: {size_mb:.1f} MB")

    if migrated > 0:
        print(f"\n{'=' * 60}")
        print("MIGRATION COMPLETE")
        print(f"{'=' * 60}")
        print()
        print("Next steps:")
        print("  1. Restart API:     sudo systemctl restart amip-api")
        print("  2. Start poller:    sudo systemctl start amip-bluetooth")
        print("  3. Verify /api/speed/snapshot returns data")
        print("  4. Once confirmed, drop old tables from amip.duckdb:")
        print()
        print("     python3 -c \"")
        print("     import duckdb")
        print(f"     con = duckdb.connect('{AMIP_DB}')")
        for t in SPEED_TABLES:
            print(f"     con.execute('DROP TABLE IF EXISTS {t}')")
        print("     con.execute('CHECKPOINT')")
        print("     con.close()\"")
    else:
        print("\nNo tables migrated (already done or not found).")


if __name__ == "__main__":
    migrate()
