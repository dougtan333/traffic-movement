"""
Refresh TIRTL Traffic Counts and Vehicle Classification data.

Queries the CKAN API for all available monthly ZIPs, downloads any that are
new or updated (file-size comparison), extracts daily CSVs, and ingests
incrementally into DuckDB using INSERT OR IGNORE.

Also refreshes the TIRTL Sites reference table on each run.

Usage:
  python scripts/refresh_tirtl.py           # check and ingest new data
  python scripts/refresh_tirtl.py --force   # re-download all months

Designed to run as part of daily_refresh.py pipeline.
Requires: bluetooth poller stopped before running (WAL lock).
"""

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
TIRTL_DIR = PROJECT_ROOT / "data_tirtl"
TRACKING_FILE = TIRTL_DIR / "tirtl_tracking.json"

CKAN_API = "https://discover.data.vic.gov.au/api/3/action/package_show?id=tirtl-traffic-counts"
DATASET_BASE = "https://opendata.transport.vic.gov.au/dataset/e2d78fb5-e16d-43b9-bcdc-607d9b4855f5/resource"
SITES_RESOURCE_ID = "1f685833-24fd-4eb0-af11-2e7cfc94da74"


def load_tracking():
    """Load tracking state: resource_id -> {size, name}."""
    if TRACKING_FILE.exists():
        return json.loads(TRACKING_FILE.read_text())
    return {}


def save_tracking(state):
    TRACKING_FILE.write_text(json.dumps(state, indent=2))


def get_remote_size(url):
    """HEAD request to get Content-Length."""
    req = Request(url, method="HEAD")
    with urlopen(req, timeout=30) as resp:
        return int(resp.headers.get("Content-Length", 0))


def download_file(url, dest):
    """Download file with progress."""
    req = Request(url)
    with urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    mb_down = downloaded // 1024 // 1024
                    mb_total = total // 1024 // 1024
                    print(f"\r    Downloading: {downloaded * 100 // total}% ({mb_down}MB / {mb_total}MB)", end="", flush=True)
        print()


def discover_resources():
    """Query CKAN API and return list of TIRTL ZIP resources."""
    print("Querying CKAN API for TIRTL resources...")
    req = Request(CKAN_API)
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    resources = []
    for r in data["result"]["resources"]:
        rid = r["id"]
        url = r["url"]
        name = r.get("name", "")
        if rid == SITES_RESOURCE_ID:
            continue
        if url.endswith(".zip") or "classification" in name.lower():
            resources.append({"id": rid, "name": name, "url": url})
            print(f"  Found: {name}")
    return resources


def refresh_sites(con):
    """Download and reload TIRTL Sites reference table."""
    print("\nRefreshing TIRTL Sites...")
    sites_url = f"{DATASET_BASE}/{SITES_RESOURCE_ID}/download/tirtl_sites.csv"
    sites_path = TIRTL_DIR / "tirtl_sites.csv"
    download_file(sites_url, sites_path)

    con.execute("DELETE FROM tirtl_sites")
    con.execute(f"""
        INSERT INTO tirtl_sites
        SELECT site::INTEGER, site_description, latitude::DOUBLE, longitude::DOUBLE
        FROM read_csv_auto('{sites_path}')
    """)
    count = con.execute("SELECT count(*) FROM tirtl_sites").fetchone()[0]
    print(f"  Sites: {count} loaded")


def ingest_zip(con, zip_path, resource_id):
    """Extract a TIRTL monthly ZIP and ingest daily CSVs."""
    extract_dir = TIRTL_DIR / f"extract_{resource_id[:8]}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    print(f"  Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # Find daily CSV files — may be nested in subdirectories
    csv_files = sorted(extract_dir.rglob("TIRTLDATA_*.csv"))
    if not csv_files:
        csv_files = sorted(f for f in extract_dir.rglob("*.csv") if "site" not in f.name.lower())

    if not csv_files:
        print(f"  WARNING: No TIRTL data CSVs found in {zip_path.name}")
        shutil.rmtree(extract_dir)
        return 0

    print(f"  Found {len(csv_files)} daily files")
    total_new = 0

    for f in csv_files:
        before = con.execute("SELECT count(*) FROM tirtl_counts").fetchone()[0]
        try:
            con.execute(f"""
                INSERT OR IGNORE INTO tirtl_counts
                SELECT
                    (date::DATE || ' ' || time_bin)::TIMESTAMP as ts_interval,
                    site::INTEGER as site_id,
                    heading,
                    vehicle_class::TINYINT,
                    SUM(volume::INTEGER) as volume,
                    CASE WHEN SUM(volume::INTEGER) > 0 THEN
                        (SUM(volume::INTEGER * (
                            CASE
                                WHEN speed_bin LIKE '%+' THEN
                                    CAST(REPLACE(REPLACE(speed_bin, 'km/hr', ''), ' +', '') AS INTEGER) + 2
                                WHEN speed_bin LIKE '%to%' THEN
                                    CAST(REPLACE(SPLIT_PART(speed_bin, ' to', 1), 'km/hr', '') AS INTEGER) + 2
                                ELSE 0
                            END
                        )) / SUM(volume::INTEGER))::SMALLINT
                    ELSE NULL END as avg_speed_kmh
                FROM read_csv_auto('{f}')
                WHERE date IS NOT NULL AND volume::INTEGER > 0
                GROUP BY 1, 2, 3, 4
            """)
        except Exception as e:
            print(f"    ERROR processing {f.name}: {e}")
            continue

        after = con.execute("SELECT count(*) FROM tirtl_counts").fetchone()[0]
        new_rows = after - before
        if new_rows > 0:
            total_new += new_rows

    con.execute("CHECKPOINT")
    shutil.rmtree(extract_dir)
    return total_new


def ensure_tables(con):
    """Create TIRTL tables if they don't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS tirtl_sites (
            site_id INTEGER PRIMARY KEY, site_description VARCHAR,
            latitude DOUBLE, longitude DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tirtl_counts (
            ts_interval TIMESTAMP NOT NULL, site_id INTEGER NOT NULL,
            heading VARCHAR(1) NOT NULL, vehicle_class TINYINT NOT NULL,
            volume INTEGER NOT NULL, avg_speed_kmh SMALLINT,
            PRIMARY KEY (ts_interval, site_id, heading, vehicle_class)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_tirtl_ts ON tirtl_counts (ts_interval)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tirtl_site ON tirtl_counts (site_id, ts_interval)")


def main():
    parser = argparse.ArgumentParser(description="Refresh TIRTL data")
    parser.add_argument("--force", action="store_true", help="Re-download all months")
    args = parser.parse_args()

    TIRTL_DIR.mkdir(exist_ok=True)
    tracking = load_tracking()

    # Discover available resources from portal
    resources = discover_resources()
    if not resources:
        print("No TIRTL ZIP resources found on portal.")
        return

    # Check which need downloading (file-size comparison)
    to_download = []
    for r in resources:
        remote_size = get_remote_size(r["url"])
        prev_size = tracking.get(r["id"], {}).get("size", 0)
        if args.force or remote_size != prev_size:
            mb_remote = remote_size // 1024 // 1024
            mb_prev = prev_size // 1024 // 1024
            print(f"  {r['name']}: {mb_remote}MB (was {mb_prev}MB) — will download")
            r["remote_size"] = remote_size
            to_download.append(r)
        else:
            print(f"  {r['name']}: unchanged — skip")

    if not to_download:
        print("\nAll TIRTL data is up to date.")
        return

    # Connect and ensure tables
    con = duckdb.connect(str(DB_PATH))
    ensure_tables(con)
    refresh_sites(con)

    # Download and ingest each updated ZIP
    grand_total = 0
    for r in to_download:
        print(f"\n--- {r['name']} ---")
        zip_path = TIRTL_DIR / f"tirtl_{r['id'][:8]}.zip"
        download_file(r["url"], zip_path)

        new_rows = ingest_zip(con, zip_path, r["id"])
        grand_total += new_rows
        print(f"  New rows ingested: {new_rows:,d}")

        # Update tracking
        tracking[r["id"]] = {"name": r["name"], "size": r["remote_size"]}
        save_tracking(tracking)
        zip_path.unlink()

    # Final stats
    con.execute("FORCE CHECKPOINT")
    stats = con.execute("""
        SELECT count(*), MIN(ts_interval)::DATE, MAX(ts_interval)::DATE,
               count(DISTINCT site_id)
        FROM tirtl_counts
    """).fetchone()
    con.close()

    print(f"\n=== TIRTL Refresh Complete ===")
    print(f"New rows this run: {grand_total:,d}")
    print(f"Total rows: {stats[0]:,d}  From: {stats[1]}  To: {stats[2]}  Sites: {stats[3]}")


if __name__ == "__main__":
    main()
