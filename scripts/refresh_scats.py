"""
Incremental SCATS Traffic Volume Refresh

Downloads the latest monthly ZIP from the VIC open data portal,
extracts only CSVs for dates not yet in the database, ingests them
into hourly_counts, updates summary tables, and refreshes the
Parquet archive.

Designed to run daily/weekly as part of daily_refresh.py.
Only new days are processed — no deletion, no full reload.

Usage:
    python scripts/refresh_scats.py          # download + ingest new days
    python scripts/refresh_scats.py --skip-download  # ingest from already-downloaded ZIPs

Source: https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data
Licence: Creative Commons Attribution 4.0
"""

import duckdb
import os
import re
import sys
import shutil
import zipfile
import tempfile
from datetime import date, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
ARCHIVE_DIR = PROJECT_ROOT / "db" / "archive"
STAGING_DIR = PROJECT_ROOT / "data_vic_new" / "scats_staging"
PORTAL_URL = "https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data"


def get_latest_db_date() -> date:
    """Return the latest SCATS date already in hourly_counts."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    result = con.execute(
        "SELECT max(ts_hour)::DATE FROM hourly_counts WHERE state = 'VIC'"
    ).fetchone()[0]
    con.close()
    return result


def find_latest_zip_url() -> tuple[str, str]:
    """Scrape the portal page and return (url, month_label) for the most recent ZIP."""
    print("  Checking VIC portal for latest SCATS data...")
    resp = requests.get(PORTAL_URL, timeout=30)
    resp.raise_for_status()

    # Find all download links matching the pattern
    pattern = r'href="(https://opendata\.transport\.vic\.gov\.au/dataset/[^"]+/download/traffic_signal_volume_data_(\w+_\d{4})\.zip)"'
    matches = re.findall(pattern, resp.text)

    if not matches:
        print("  ERROR: No SCATS ZIP links found on portal page")
        return None, None

    # The first match on the page is the most recent (portal lists newest first)
    url, month_label = matches[0]
    print(f"  Latest available: {month_label} -> {url[:80]}...")
    return url, month_label


def download_zip(url: str, month_label: str) -> Path:
    """Download the ZIP to staging. Skips if already downloaded."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = STAGING_DIR / f"traffic_signal_volume_data_{month_label}.zip"

    if zip_path.exists():
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"  Already downloaded: {zip_path.name} ({size_mb:.0f} MB)")
        return zip_path

    print(f"  Downloading {zip_path.name}...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(zip_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Downloaded: {size_mb:.0f} MB")
    return zip_path


def extract_new_csvs(zip_path: Path, latest_db_date: date) -> Path:
    """Extract only CSVs for dates after latest_db_date. Returns temp dir with CSVs."""
    extract_dir = STAGING_DIR / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    new_count = 0
    skipped = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith('.csv') or 'VSDATA_' not in name:
                continue
            # Parse date from filename: VSDATA_20260314.csv
            match = re.search(r'VSDATA_(\d{8})\.csv', name)
            if not match:
                continue
            csv_date = datetime.strptime(match.group(1), '%Y%m%d').date()

            if csv_date <= latest_db_date:
                skipped += 1
                continue

            # Extract just this CSV
            zf.extract(name, extract_dir)
            new_count += 1

    print(f"  Extracted {new_count} new day CSVs (skipped {skipped} already in DB)")
    return extract_dir


def ingest_new_days(extract_dir: Path) -> int:
    """Ingest extracted CSVs into hourly_counts. Returns rows inserted."""
    # Find the CSV files (may be in a subdirectory from ZIP structure)
    csv_files = list(extract_dir.rglob("VSDATA_*.csv"))
    if not csv_files:
        print("  No new CSVs to ingest")
        return 0

    # Use the directory containing the CSVs for the glob
    csv_dir = csv_files[0].parent

    con = duckdb.connect(str(DB_PATH), read_only=False)
    try:
        con.execute(f"""
            CREATE OR REPLACE TEMP VIEW raw_scats AS
            SELECT * FROM read_csv_auto('{csv_dir}/VSDATA_*.csv', union_by_name=true)
        """)

        # Build hourly aggregation: each hour = sum of 4 consecutive 15-min intervals
        hour_exprs = []
        for h in range(24):
            v_start = h * 4
            cols = " + ".join(f"COALESCE(V{v_start+i:02d}, 0)" for i in range(4))
            hour_exprs.append(f"SUM({cols}) AS h{h:02d}")
        hour_select = ",\n            ".join(hour_exprs)

        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE hourly_by_site AS
            SELECT NB_SCATS_SITE AS site_no,
                   QT_INTERVAL_COUNT AS obs_date,
                   {hour_select}
            FROM raw_scats
            GROUP BY NB_SCATS_SITE, QT_INTERVAL_COUNT
        """)

        # Unpivot hours and join to stations — plain INSERT (no duplicates since we only extract new days)
        values_list = ", ".join(f"({h}, h{h:02d})" for h in range(24))
        con.execute(f"""
            INSERT INTO hourly_counts
            SELECT
                s.station_id,
                CAST(obs_date AS TIMESTAMP) + INTERVAL (hr.hour_num) HOUR AS ts_hour,
                hr.vehicle_count::INTEGER,
                'VIC' AS state,
                ISODOW(CAST(obs_date AS DATE))::TINYINT AS day_of_week,
                hr.hour_num::TINYINT AS hour_of_day,
                ISODOW(CAST(obs_date AS DATE)) <= 5 AS is_weekday
            FROM hourly_by_site h
            CROSS JOIN LATERAL (VALUES {values_list}) AS hr(hour_num, vehicle_count)
            INNER JOIN stations s
                ON s.source_id = CAST(h.site_no AS VARCHAR) AND s.state = 'VIC'
            WHERE hr.vehicle_count > 0
        """)

        # Count what we inserted
        date_range = con.execute("SELECT min(obs_date), max(obs_date) FROM hourly_by_site").fetchone()
        if date_range[0] is None:
            con.close()
            return 0
        count = con.execute(f"""
            SELECT count(*) FROM hourly_counts
            WHERE state = 'VIC'
              AND CAST(ts_hour AS DATE) BETWEEN '{date_range[0]}' AND '{date_range[1]}'
        """).fetchone()[0]

        con.execute("CHECKPOINT")
        print(f"  Ingested {count:,} rows for {date_range[0]} to {date_range[1]}")
    finally:
        con.close()
    return count


def update_parquet_archive(year: int = None):
    """Re-export the current year's Parquet file."""
    if year is None:
        year = date.today().year
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = ARCHIVE_DIR / f"hourly_counts_{year}.parquet"

    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(f"""
        COPY (SELECT * FROM hourly_counts WHERE EXTRACT(YEAR FROM ts_hour) = {year})
        TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    size_mb = os.path.getsize(str(out)) / (1024 * 1024)
    print(f"  Parquet archive updated: {out.name} ({size_mb:.0f} MB)")


def refresh(skip_download=False, skip_summaries=False):
    """Full incremental refresh: download, extract new days, ingest, update summaries."""
    print("SCATS Incremental Refresh")
    print("=" * 50)

    # 1. What do we have?
    latest_db = get_latest_db_date()
    print(f"  Latest in DB: {latest_db}")

    if not skip_download:
        # 2. Find and download latest ZIP
        url, month_label = find_latest_zip_url()
        if not url:
            return False
        zip_path = download_zip(url, month_label)
    else:
        # Use whatever ZIP is already in staging
        zips = sorted(STAGING_DIR.glob("*.zip"))
        if not zips:
            print("  ERROR: No ZIPs in staging directory")
            return False
        zip_path = zips[-1]
        print(f"  Using existing: {zip_path.name}")

    # 3. Extract only new days
    extract_dir = extract_new_csvs(zip_path, latest_db)

    # 4. Ingest
    rows = ingest_new_days(extract_dir)
    if rows == 0:
        print("  No new data to ingest — DB is up to date")
        return True

    # 5. Update summary tables (unless caller handles this separately)
    if not skip_summaries:
        print("  Updating summary tables...")
        import subprocess
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_summaries.py"), "--append"],
            cwd=str(PROJECT_ROOT), check=True
        )

    # 6. Update Parquet archive
    print("  Updating Parquet archive...")
    update_parquet_archive()

    # 7. Cleanup extracted CSVs
    extract_dir_to_clean = STAGING_DIR / "extract"
    if extract_dir_to_clean.exists():
        shutil.rmtree(extract_dir_to_clean)

    # Final check
    new_latest = get_latest_db_date()
    print(f"\n  DB updated: {latest_db} -> {new_latest}")
    print(f"  New days added: {(new_latest - latest_db).days}")
    print("=" * 50)
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Incremental SCATS refresh")
    parser.add_argument("--skip-download", action="store_true",
                        help="Use already-downloaded ZIP in staging")
    parser.add_argument("--skip-summaries", action="store_true",
                        help="Skip summary table update (when called from daily_refresh)")
    args = parser.parse_args()
    success = refresh(skip_download=args.skip_download, skip_summaries=args.skip_summaries)
    sys.exit(0 if success else 1)
