"""
AMIP Database Backup

Creates a timestamped copy of amip.duckdb. Run daily via cron or
as part of daily_refresh.py. Keeps the most recent N backups and
deletes older ones.

Usage:
  python scripts/backup_db.py              # backup now
  python scripts/backup_db.py --keep 7     # keep last 7 backups (default)

The backup is a simple file copy — DuckDB read-only connections are
safe to copy from while the API is running. The Bluetooth poller
does NOT need to be stopped for backups (it connects/disconnects
per cycle and the copy is atomic at the filesystem level).
"""

import shutil
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
BACKUP_DIR = PROJECT_ROOT / "db" / "backups"
AEST = timezone(timedelta(hours=10))


def backup(keep: int = 7):
    """Copy amip.duckdb to db/backups/ with a timestamp suffix."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        return False

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(AEST).strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"amip_{ts}.duckdb"

    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"Backing up {DB_PATH.name} ({size_mb:.0f} MB) -> {dest.name}")

    shutil.copy2(str(DB_PATH), str(dest))
    print(f"Backup complete: {dest}")

    # Prune old backups
    backups = sorted(BACKUP_DIR.glob("amip_*.duckdb"), reverse=True)
    if len(backups) > keep:
        for old in backups[keep:]:
            old.unlink()
            print(f"Pruned old backup: {old.name}")

    print(f"Backups retained: {min(len(backups), keep)}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AMIP database backup")
    parser.add_argument("--keep", type=int, default=7,
                        help="Number of backups to retain (default 7)")
    args = parser.parse_args()
    success = backup(keep=args.keep)
    sys.exit(0 if success else 1)
