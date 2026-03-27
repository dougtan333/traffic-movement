"""
Incremental SCATS Traffic Volume Refresh

Downloads the latest monthly ZIP from the VIC open data portal,
extracts only CSVs for dates not yet in the database, ingests them
into temp tables, appends to summary tables, and updates the
Parquet archive.

Does NOT require the hourly_counts table (dropped in DEC-032).
Latest date is read from daily_station_summary. New data flows
directly into summary tables and Parquet archive.

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
    """Return the latest SCATS date from daily_station_summary.

    Previously read from hourly_counts (dropped in DEC-032).
    daily_station_summary is always up-to-date because refresh_scats
    appends to it directly during ingestion.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    result = con.execute(
        "SELECT max(day) FROM daily_station_summary"
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
    """Ingest extracted CSVs: build hourly data in temp tables, then
    append directly to summary tables and update Parquet archive.
    Does NOT require the hourly_counts table to exist."""
    csv_files = list(extract_dir.rglob("VSDATA_*.csv"))
    if not csv_files:
        print("  No new CSVs to ingest")
        return 0

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

        # Unpivot into full hourly rows in a temp table
        values_list = ", ".join(f"({h}, h{h:02d})" for h in range(24))
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE new_hourly AS
            SELECT
                s.station_id,
                CAST(obs_date AS TIMESTAMP) + INTERVAL (hr.hour_num) HOUR AS ts_hour,
                hr.vehicle_count::INTEGER AS vehicle_count,
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

        date_range = con.execute("SELECT min(obs_date), max(obs_date) FROM hourly_by_site").fetchone()
        if date_range[0] is None:
            con.close()
            return 0

        total_rows = con.execute("SELECT count(*) FROM new_hourly").fetchone()[0]
        print(f"  Processed {total_rows:,} hourly rows for {date_range[0]} to {date_range[1]}")

        # Append to daily_station_summary (metro core only)
        con.execute("""
            INSERT INTO daily_station_summary
            SELECT nh.station_id,
                   CAST(nh.ts_hour AS DATE) as day,
                   SUM(nh.vehicle_count)::INT as daily_total,
                   SUM(CASE WHEN nh.hour_of_day BETWEEN 7 AND 17 THEN nh.vehicle_count ELSE 0 END)::INT as biz_hours_total,
                   ISODOW(CAST(nh.ts_hour AS DATE)) as day_of_week,
                   CASE WHEN ISODOW(CAST(nh.ts_hour AS DATE)) <= 5 THEN true ELSE false END as is_weekday,
                   EXTRACT(YEAR FROM CAST(nh.ts_hour AS DATE))::INT as year,
                   EXTRACT(MONTH FROM CAST(nh.ts_hour AS DATE))::INT as month
            FROM new_hourly nh
            INNER JOIN metro_core_stations m ON nh.station_id = m.station_id
            GROUP BY nh.station_id, CAST(nh.ts_hour AS DATE)
        """)
        ds_count = con.execute("SELECT count(*) FROM daily_station_summary").fetchone()[0]
        ds_latest = con.execute("SELECT max(day) FROM daily_station_summary").fetchone()[0]
        print(f"  daily_station_summary: {ds_count:,} rows, latest = {ds_latest}")

        # Append to hourly_city_summary (all stations)
        con.execute("""
            INSERT INTO hourly_city_summary
            SELECT CAST(nh.ts_hour AS DATE) as day,
                   nh.hour_of_day,
                   AVG(nh.vehicle_count)::INT as avg_count,
                   SUM(nh.vehicle_count)::BIGINT as total_count,
                   COUNT(DISTINCT nh.station_id)::INT as stations,
                   ISODOW(CAST(nh.ts_hour AS DATE)) as day_of_week,
                   CASE WHEN ISODOW(CAST(nh.ts_hour AS DATE)) <= 5 THEN true ELSE false END as is_weekday,
                   EXTRACT(YEAR FROM CAST(nh.ts_hour AS DATE))::INT as year
            FROM new_hourly nh
            GROUP BY CAST(nh.ts_hour AS DATE), nh.hour_of_day
        """)
        hc_count = con.execute("SELECT count(*) FROM hourly_city_summary").fetchone()[0]
        print(f"  hourly_city_summary: {hc_count:,} rows")

        # Append new hourly rows to Parquet archive (current year)
        year = date.today().year
        archive_path = ARCHIVE_DIR / f"hourly_counts_{year}.parquet"
        if archive_path.exists():
            # Merge: read existing + new, write combined
            con.execute(f"""
                COPY (
                    SELECT * FROM read_parquet('{archive_path}')
                    UNION ALL
                    SELECT * FROM new_hourly WHERE EXTRACT(YEAR FROM ts_hour) = {year}
                ) TO '{archive_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """)
        else:
            con.execute(f"""
                COPY (SELECT * FROM new_hourly WHERE EXTRACT(YEAR FROM ts_hour) = {year})
                TO '{archive_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """)
        pq_size = os.path.getsize(str(archive_path)) / (1024*1024)
        print(f"  Parquet archive: {archive_path.name} ({pq_size:.0f} MB)")

        con.execute("CHECKPOINT")
        print(f"  Ingested {total_rows:,} rows for {date_range[0]} to {date_range[1]}")
    finally:
        con.close()
    return total_rows


def update_parquet_archive(year: int = None):
    """Re-export a year's Parquet file.

    Note: This is a standalone utility. The main refresh() path already
    appends to the Parquet archive during ingestion. This function is
    only needed if you want to rebuild a year's archive from scratch,
    which requires the hourly_counts table to exist (it was dropped
    in DEC-032). For normal daily operation, this is never called.
    """
    if year is None:
        year = date.today().year
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = ARCHIVE_DIR / f"hourly_counts_{year}.parquet"

    if out.exists():
        size_mb = os.path.getsize(str(out)) / (1024 * 1024)
        print(f"  Parquet archive already exists: {out.name} ({size_mb:.0f} MB)")
        print(f"  Skipping — archive is updated incrementally during refresh()")
    else:
        print(f"  ERROR: No archive for {year} and hourly_counts table is dropped.")
        print(f"  Cannot rebuild from scratch. Re-ingest from SCATS ZIPs if needed.")


def refresh(skip_download=False):
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

    # 4. Ingest — updates summaries and Parquet archive directly
    rows = ingest_new_days(extract_dir)
    if rows == 0:
        print("  No new data to ingest — DB is up to date")
        return True

    # 5. Cleanup extracted CSVs
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
    args = parser.parse_args()
    success = refresh(skip_download=args.skip_download)
    sys.exit(0 if success else 1)
