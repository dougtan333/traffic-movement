"""
Data inspection script for AMIP V1
Inspects NSW + VIC raw data files, checks joins, coverage, and quality.
Outputs a structured report to stdout.
"""
import duckdb
import os
from pyproj import Transformer

BASE = '/Users/doug/Projects/Traffic Movement'
con = duckdb.connect()

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

# ─────────────────────────────────────────────────────────────
# 1. NSW STATION REFERENCE
# ─────────────────────────────────────────────────────────────
section("1. NSW STATION REFERENCE")
ref_path = f"{BASE}/road_traffic_counts_station_reference.csv"

r = con.sql(f"""
    SELECT count(*) as total,
           count(DISTINCT station_key) as unique_keys,
           count(wgs84_latitude) as has_coords,
           count(road_name) as has_road
    FROM read_csv_auto('{ref_path}')
""").fetchone()
print(f"Total rows: {r[0]}")
print(f"Unique station_keys: {r[1]}")
print(f"Has coordinates: {r[2]}")
print(f"Has road_name: {r[3]}")

# By region
print("\nStations by RMS region:")
for row in con.sql(f"""
    SELECT rms_region, count(*) as cnt,
           sum(CASE WHEN permanent_station = 1 THEN 1 ELSE 0 END) as permanent
    FROM read_csv_auto('{ref_path}')
    GROUP BY rms_region ORDER BY cnt DESC
""").fetchall():
    print(f"  {str(row[0]):20s}  total={row[1]:5d}  permanent={row[2]:5d}")

# Sydney detail
print("\nSydney permanent stations by road hierarchy:")
for row in con.sql(f"""
    SELECT road_functional_hierarchy, count(*) as cnt
    FROM read_csv_auto('{ref_path}')
    WHERE rms_region = 'Sydney' AND permanent_station = 1
    GROUP BY road_functional_hierarchy ORDER BY cnt DESC
""").fetchall():
    print(f"  {str(row[0]):30s}  {row[1]}")

# ─────────────────────────────────────────────────────────────
# 2. NSW HOURLY COUNTS - all 5 files
# ─────────────────────────────────────────────────────────────
section("2. NSW HOURLY COUNTS")
nsw_dir = f"{BASE}/road_traffic_counts_hourly_permanent"
nsw_files = sorted([f for f in os.listdir(nsw_dir) if f.endswith('.csv')])
print(f"Files found: {len(nsw_files)}")

# Stats across all files
r = con.sql(f"""
    SELECT count(*) as rows,
           count(DISTINCT station_key) as stations,
           min(date) as min_date,
           max(date) as max_date,
           avg(daily_total) as avg_daily,
           sum(CASE WHEN daily_total = 0 OR daily_total IS NULL THEN 1 ELSE 0 END) as zero_days,
           count(DISTINCT year) as years_covered
    FROM read_csv_auto('{nsw_dir}/*.csv', union_by_name=true)
""").fetchone()
print(f"Total rows: {r[0]:,d}")
print(f"Unique stations: {r[1]}")
print(f"Date range: {r[2]} to {r[3]}")
print(f"Avg daily total: {r[4]:.0f}")
print(f"Zero/null daily total rows: {r[5]:,d}")
print(f"Years covered: {r[6]}")

# Check how many stations have station_key that matches the reference
print("\nJoin check — hourly station_keys found in reference:")
r = con.sql(f"""
    WITH hourly_keys AS (
        SELECT DISTINCT station_key FROM read_csv_auto('{nsw_dir}/*.csv', union_by_name=true)
    ),
    ref_keys AS (
        SELECT DISTINCT station_key FROM read_csv_auto('{ref_path}')
    )
    SELECT 
        (SELECT count(*) FROM hourly_keys) as hourly_unique,
        (SELECT count(*) FROM hourly_keys h WHERE EXISTS (SELECT 1 FROM ref_keys r WHERE r.station_key = h.station_key)) as matched,
        (SELECT count(*) FROM hourly_keys h WHERE NOT EXISTS (SELECT 1 FROM ref_keys r WHERE r.station_key = h.station_key)) as unmatched
""").fetchone()
print(f"  Hourly unique keys: {r[0]}")
print(f"  Matched to reference: {r[1]}")
print(f"  Unmatched (orphans): {r[2]}")

# Sydney-only hourly data
print("\nSydney-only hourly data (joined to reference, permanent only):")
r = con.sql(f"""
    SELECT count(*) as rows,
           count(DISTINCT h.station_key) as stations,
           min(h.date) as min_date,
           max(h.date) as max_date
    FROM read_csv_auto('{nsw_dir}/*.csv', union_by_name=true) h
    INNER JOIN read_csv_auto('{ref_path}') r ON h.station_key = r.station_key
    WHERE r.rms_region = 'Sydney' AND r.permanent_station = 1
""").fetchone()
print(f"  Rows: {r[0]:,d}")
print(f"  Stations: {r[1]}")
print(f"  Date range: {r[2]} to {r[3]}")

# Year distribution for Sydney permanent
print("\nSydney permanent — rows per year:")
for row in con.sql(f"""
    SELECT h.year, count(*) as rows, count(DISTINCT h.station_key) as stations
    FROM read_csv_auto('{nsw_dir}/*.csv', union_by_name=true) h
    INNER JOIN read_csv_auto('{ref_path}') r ON h.station_key = r.station_key
    WHERE r.rms_region = 'Sydney' AND r.permanent_station = 1
    GROUP BY h.year ORDER BY h.year
""").fetchall():
    print(f"  {row[0]}  rows={row[1]:>8,d}  stations={row[2]}")

# ─────────────────────────────────────────────────────────────
# 3. VIC SCATS VOLUME DATA
# ─────────────────────────────────────────────────────────────
section("3. VIC SCATS VOLUME DATA")
vic_dir = f"{BASE}/traffic_signal_volume_data_march_2026"
vic_files = sorted([f for f in os.listdir(vic_dir) if f.endswith('.csv')])
print(f"Files found: {len(vic_files)} (days of March 2026)")

# Inspect one file
r = con.sql(f"""
    SELECT count(*) as rows,
           count(DISTINCT NB_SCATS_SITE) as sites,
           count(DISTINCT NB_DETECTOR) as detectors,
           min(QT_INTERVAL_COUNT) as min_date,
           max(QT_INTERVAL_COUNT) as max_date,
           avg(QT_VOLUME_24HOUR) as avg_24hr,
           sum(CASE WHEN QT_VOLUME_24HOUR = 0 THEN 1 ELSE 0 END) as zero_24hr
    FROM read_csv_auto('{vic_dir}/*.csv', union_by_name=true)
""").fetchone()
print(f"Total rows (all days): {r[0]:,d}")
print(f"Unique SCATS sites: {r[1]}")
print(f"Unique detector IDs: {r[2]}")
print(f"Date range: {r[3]} to {r[4]}")
print(f"Avg 24hr volume per detector-day: {r[5]:.0f}")
print(f"Zero 24hr volume rows: {r[6]:,d} ({r[6]/r[0]*100:.1f}%)")

# Regions
print("\nSCATS sites by NM_REGION:")
for row in con.sql(f"""
    SELECT NM_REGION, count(DISTINCT NB_SCATS_SITE) as sites
    FROM read_csv_auto('{vic_dir}/*.csv', union_by_name=true)
    GROUP BY NM_REGION ORDER BY sites DESC
""").fetchall():
    print(f"  {str(row[0]):10s}  sites={row[1]}")

# Detectors per site distribution
print("\nDetectors per site distribution:")
for row in con.sql(f"""
    WITH site_det AS (
        SELECT NB_SCATS_SITE, count(DISTINCT NB_DETECTOR) as det_count
        FROM read_csv_auto('{vic_dir}/VSDATA_20260301.csv')
        GROUP BY NB_SCATS_SITE
    )
    SELECT 
        min(det_count) as min_det,
        max(det_count) as max_det,
        avg(det_count)::int as avg_det,
        median(det_count)::int as med_det,
        count(*) as total_sites
    FROM site_det
""").fetchall():
    print(f"  min={row[0]}  max={row[1]}  avg={row[2]}  median={row[3]}  total_sites={row[4]}")

# ─────────────────────────────────────────────────────────────
# 4. VIC TRAFFIC LIGHTS (site reference)
# ─────────────────────────────────────────────────────────────
section("4. VIC TRAFFIC LIGHTS REFERENCE")
tl_path = f"{BASE}/Traffic_Lights.csv"

r = con.sql(f"""
    SELECT count(*) as total,
           count(DISTINCT SITE_NO) as unique_sites,
           count(CASE WHEN X != 0 AND Y != 0 THEN 1 END) as has_coords,
           count(SITE_NAME) as has_name
    FROM read_csv_auto('{tl_path}')
""").fetchone()
print(f"Total rows: {r[0]}")
print(f"Unique SITE_NO: {r[1]}")
print(f"Has non-zero coords: {r[2]}")
print(f"Has site name: {r[3]}")

# Join check: SCATS sites vs Traffic Lights
print("\nJoin check — SCATS NB_SCATS_SITE vs Traffic Lights SITE_NO:")
r = con.sql(f"""
    WITH scats_sites AS (
        SELECT DISTINCT NB_SCATS_SITE FROM read_csv_auto('{vic_dir}/VSDATA_20260301.csv')
    ),
    tl_sites AS (
        SELECT DISTINCT SITE_NO FROM read_csv_auto('{tl_path}')
    )
    SELECT 
        (SELECT count(*) FROM scats_sites) as scats_unique,
        (SELECT count(*) FROM scats_sites s WHERE EXISTS (SELECT 1 FROM tl_sites t WHERE t.SITE_NO = s.NB_SCATS_SITE)) as matched,
        (SELECT count(*) FROM scats_sites s WHERE NOT EXISTS (SELECT 1 FROM tl_sites t WHERE t.SITE_NO = s.NB_SCATS_SITE)) as unmatched
""").fetchone()
print(f"  SCATS unique sites: {r[0]}")
print(f"  Matched to Traffic Lights: {r[1]}")
print(f"  Unmatched (no location data): {r[2]}")
print(f"  Match rate: {r[1]/r[0]*100:.1f}%")

# Coordinate reprojection check
print("\nCoordinate reprojection test (MGA Zone 55 → WGS84):")
sample = con.sql(f"""
    SELECT SITE_NO, SITE_NAME, X, Y 
    FROM read_csv_auto('{tl_path}')
    WHERE X != 0 AND Y != 0
    LIMIT 5
""").fetchall()

# Try MGA Zone 55 (EPSG:28355) - most of Melbourne
transformer = Transformer.from_crs("EPSG:28355", "EPSG:4326", always_xy=True)
for row in sample:
    lon, lat = transformer.transform(row[2], row[3])
    # Check if result looks like Melbourne area (-37 to -38 lat, 144 to 146 lon)
    mel_area = -39 < lat < -36 and 143 < lon < 147
    print(f"  SITE {row[0]:5d}  {row[1]:45s}  → ({lat:.5f}, {lon:.5f})  {'✓ Melbourne' if mel_area else '✗ Check CRS'}")

# ─────────────────────────────────────────────────────────────
# 5. DATA QUALITY SUMMARY
# ─────────────────────────────────────────────────────────────
section("5. DATA QUALITY SUMMARY")

# NSW null checks
print("NSW hourly — null/empty field rates (sample file 0):")
r = con.sql(f"""
    SELECT count(*) as total,
           sum(CASE WHEN station_key IS NULL THEN 1 ELSE 0 END) as null_key,
           sum(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_date,
           sum(CASE WHEN daily_total IS NULL THEN 1 ELSE 0 END) as null_daily,
           sum(CASE WHEN hour_08 IS NULL THEN 1 ELSE 0 END) as null_h08,
           sum(CASE WHEN hour_17 IS NULL THEN 1 ELSE 0 END) as null_h17
    FROM read_csv_auto('{nsw_dir}/road_traffic_counts_hourly_permanent0.csv')
""").fetchone()
print(f"  Total rows: {r[0]:,d}")
print(f"  Null station_key: {r[1]:,d}")
print(f"  Null date: {r[2]:,d}")
print(f"  Null daily_total: {r[3]:,d}")
print(f"  Null hour_08: {r[4]:,d}")
print(f"  Null hour_17: {r[5]:,d}")

# VIC null checks
print("\nVIC SCATS — null/zero field rates (1 March 2026):")
r = con.sql(f"""
    SELECT count(*) as total,
           sum(CASE WHEN NB_SCATS_SITE IS NULL THEN 1 ELSE 0 END) as null_site,
           sum(CASE WHEN QT_VOLUME_24HOUR = 0 THEN 1 ELSE 0 END) as zero_vol,
           sum(CASE WHEN QT_VOLUME_24HOUR > 0 THEN 1 ELSE 0 END) as active
    FROM read_csv_auto('{vic_dir}/VSDATA_20260301.csv')
""").fetchone()
print(f"  Total rows: {r[0]:,d}")
print(f"  Null site: {r[1]:,d}")
print(f"  Zero 24hr volume: {r[2]:,d} ({r[2]/r[0]*100:.1f}%)")
print(f"  Active (>0 volume): {r[3]:,d} ({r[3]/r[0]*100:.1f}%)")

print("\n" + "="*70)
print("  INSPECTION COMPLETE")
print("="*70)

con.close()
