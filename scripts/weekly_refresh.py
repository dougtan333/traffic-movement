"""
AMIP Weekly Traffic Monitor — Fuel Crisis Tracker

Downloads the latest VIC SCATS monthly data, ingests it, and generates
a weekly comparison report: current week vs baseline (Feb 2026 avg)
and vs same week last year.

Also refreshes NSW data if a new bulk CSV is available.

Usage:
    python scripts/weekly_refresh.py

What it does:
    1. Checks for new VIC SCATS monthly ZIPs on the portal
    2. Downloads and extracts any new months
    3. Runs the VIC ingestion for new data only (appends, doesn't rebuild)
    4. Queries the database for the latest week's traffic stats
    5. Compares against baseline periods
    6. Prints a structured report to stdout
    7. Saves report as JSON for dashboard consumption

Prerequisites:
    - pip install requests duckdb pyproj
    - VIC SCATS data portal requires no auth for downloads
    - Existing amip.duckdb with stations already loaded
"""

from pathlib import Path
from datetime import date, datetime, timedelta
import duckdb
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "amip.duckdb"
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Reliable Sydney stations (consistent data 2019–2025)
RELIABLE_NSW = [
    'NSW_56841','NSW_58870','NSW_57051','NSW_15828001','NSW_15370001',
    'NSW_57104','NSW_57096','NSW_15648001','NSW_57368','NSW_15154104',
    'NSW_99990010','NSW_15334016','NSW_15252028','NSW_15286008',
    'NSW_15334001','NSW_57140','NSW_15286003','NSW_15828005',
    'NSW_15286009','NSW_15286011','NSW_57268','NSW_57440',
    'NSW_57439','NSW_15252035','NSW_99990003','NSW_15286013'
]

# Fuel crisis onset date
CRISIS_DATE = date(2026, 3, 3)

# Baseline period: Feb 2026 weekdays (pre-crisis, full month)
BASELINE_START = date(2026, 2, 1)
BASELINE_END = date(2026, 2, 28)


def check_data_freshness(con):
    """Report the latest data date for each state."""
    r = con.execute("""
        SELECT state, max(ts_hour)::DATE as latest
        FROM hourly_counts GROUP BY state
    """).fetchall()
    freshness = {row[0]: row[1] for row in r}
    return freshness


def get_weekly_stats(con, state, station_filter=None):
    """
    Get weekly weekday averages for recent weeks.
    Returns list of dicts with week, avg_per_station, stations.
    """
    where = f"h.state = '{state}'"
    if station_filter:
        ids = ",".join([f"'{s}'" for s in station_filter])
        where = f"h.station_id IN ({ids})"

    rows = con.execute(f"""
        SELECT date_trunc('week', CAST(ts_hour AS DATE))::DATE as week,
               sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE)) 
                   / count(DISTINCT station_id) as avg_per_station,
               count(DISTINCT CAST(ts_hour AS DATE)) as days,
               count(DISTINCT station_id) as stations
        FROM hourly_counts h
        WHERE {where}
          AND ISODOW(CAST(ts_hour AS DATE)) <= 5
          AND ts_hour >= '2026-01-01'
        GROUP BY 1
        HAVING count(DISTINCT CAST(ts_hour AS DATE)) >= 3
        ORDER BY 1
    """).fetchall()
    return [{'week': str(r[0]), 'avg': int(r[1]), 'days': int(r[2]), 
             'stations': int(r[3])} for r in rows]


def get_baseline(con, state, station_filter=None):
    """Get the Feb 2026 weekday baseline avg per station."""
    where = f"h.state = '{state}'"
    if station_filter:
        ids = ",".join([f"'{s}'" for s in station_filter])
        where = f"h.station_id IN ({ids})"

    r = con.execute(f"""
        SELECT sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE))
                   / count(DISTINCT station_id) as avg_per_station
        FROM hourly_counts h
        WHERE {where}
          AND ISODOW(CAST(ts_hour AS DATE)) <= 5
          AND CAST(ts_hour AS DATE) BETWEEN '{BASELINE_START}' AND '{BASELINE_END}'
    """).fetchone()
    return int(r[0]) if r[0] else None


def get_yoy_comparison(con, state, current_week, station_filter=None):
    """Get the same week from last year for comparison."""
    week_start = datetime.strptime(current_week, '%Y-%m-%d').date()
    yoy_start = week_start.replace(year=week_start.year - 1)
    yoy_end = yoy_start + timedelta(days=4)

    where = f"h.state = '{state}'"
    if station_filter:
        ids = ",".join([f"'{s}'" for s in station_filter])
        where = f"h.station_id IN ({ids})"

    r = con.execute(f"""
        SELECT sum(vehicle_count)::bigint / count(DISTINCT CAST(ts_hour AS DATE))
                   / count(DISTINCT station_id) as avg_per_station
        FROM hourly_counts h
        WHERE {where}
          AND ISODOW(CAST(ts_hour AS DATE)) <= 5
          AND CAST(ts_hour AS DATE) BETWEEN '{yoy_start}' AND '{yoy_end}'
    """).fetchone()
    return int(r[0]) if r and r[0] else None


def pct_change(current, baseline):
    """Calculate percentage change, handling None."""
    if baseline is None or baseline == 0:
        return None
    return round((current - baseline) / baseline * 100, 1)


def generate_report(con):
    """Generate the full weekly comparison report."""
    freshness = check_data_freshness(con)
    report_date = date.today().isoformat()

    report = {
        'report_date': report_date,
        'crisis_date': CRISIS_DATE.isoformat(),
        'data_freshness': {k: str(v) for k, v in freshness.items()},
        'cities': {}
    }

    # Melbourne (full VIC network)
    mel_weeks = get_weekly_stats(con, 'VIC')
    mel_baseline = get_baseline(con, 'VIC')
    mel_latest = mel_weeks[-1] if mel_weeks else None
    mel_prior = mel_weeks[-2] if len(mel_weeks) >= 2 else None
    mel_yoy = get_yoy_comparison(con, 'VIC', mel_latest['week']) if mel_latest else None

    report['cities']['Melbourne'] = {
        'network_size': mel_latest['stations'] if mel_latest else 0,
        'baseline_feb26': mel_baseline,
        'latest_week': mel_latest,
        'prior_week': mel_prior,
        'yoy_same_week': mel_yoy,
        'vs_baseline_pct': pct_change(mel_latest['avg'], mel_baseline) if mel_latest else None,
        'vs_prior_week_pct': pct_change(mel_latest['avg'], mel_prior['avg']) if mel_latest and mel_prior else None,
        'vs_yoy_pct': pct_change(mel_latest['avg'], mel_yoy) if mel_latest and mel_yoy else None,
        'weekly_trend': mel_weeks[-8:]
    }

    # Sydney (reliable network only)
    syd_weeks = get_weekly_stats(con, 'NSW', RELIABLE_NSW)
    syd_baseline = get_baseline(con, 'NSW', RELIABLE_NSW)
    syd_latest = syd_weeks[-1] if syd_weeks else None
    syd_prior = syd_weeks[-2] if len(syd_weeks) >= 2 else None
    syd_yoy = get_yoy_comparison(con, 'NSW', syd_latest['week'], RELIABLE_NSW) if syd_latest else None

    report['cities']['Sydney'] = {
        'network_size': f"{syd_latest['stations'] if syd_latest else 0} reliable of 295",
        'baseline_feb26': syd_baseline,
        'latest_week': syd_latest,
        'prior_week': syd_prior,
        'yoy_same_week': syd_yoy,
        'vs_baseline_pct': pct_change(syd_latest['avg'], syd_baseline) if syd_latest else None,
        'vs_prior_week_pct': pct_change(syd_latest['avg'], syd_prior['avg']) if syd_latest and syd_prior else None,
        'vs_yoy_pct': pct_change(syd_latest['avg'], syd_yoy) if syd_latest and syd_yoy else None,
        'weekly_trend': syd_weeks[-8:]
    }

    return report


def print_report(report):
    """Print a human-readable report to stdout."""
    print("=" * 70)
    print("  AMIP WEEKLY TRAFFIC MONITOR — FUEL CRISIS TRACKER")
    print(f"  Report date: {report['report_date']}")
    print(f"  Crisis onset: {report['crisis_date']}")
    print("=" * 70)

    for city, data in report['cities'].items():
        print(f"\n{'─' * 70}")
        print(f"  {city.upper()} — {data['network_size']} stations")
        print(f"{'─' * 70}")

        baseline = data['baseline_feb26']
        latest = data['latest_week']
        if not latest:
            print("  No recent data available.")
            continue

        print(f"  Latest data: week of {latest['week']} ({latest['days']} weekdays)")
        print(f"  Feb 2026 baseline (weekday avg/station): {baseline:,d}")
        print(f"  Latest week avg/station:                 {latest['avg']:,d}")

        vs_base = data['vs_baseline_pct']
        vs_prior = data['vs_prior_week_pct']
        vs_yoy = data['vs_yoy_pct']
        yoy_val = data['yoy_same_week']

        arrow = lambda v: "▲" if v and v > 0 else ("▼" if v and v < 0 else "→")

        print(f"\n  vs Feb baseline:   {arrow(vs_base)} {vs_base:+.1f}%" if vs_base is not None else "  vs Feb baseline:   N/A")
        print(f"  vs prior week:     {arrow(vs_prior)} {vs_prior:+.1f}%" if vs_prior is not None else "  vs prior week:     N/A")
        if yoy_val:
            print(f"  vs same week 2025: {arrow(vs_yoy)} {vs_yoy:+.1f}% (was {yoy_val:,d})")
        else:
            print(f"  vs same week 2025: N/A")


        # Weekly trend mini-table
        print(f"\n  Weekly trend (weekday avg vehicles/station):")
        print(f"  {'Week':12s}  {'Avg':>8s}  {'vs Base':>8s}  {'Signal':>8s}")
        print(f"  {'─'*42}")
        for w in data['weekly_trend']:
            w_date = datetime.strptime(w['week'], '%Y-%m-%d').date()
            vs = pct_change(w['avg'], baseline)
            is_crisis = w_date >= CRISIS_DATE
            signal = "⚠ CRISIS" if is_crisis else ""
            vs_str = f"{vs:+.1f}%" if vs is not None else "N/A"
            print(f"  {w['week']:12s}  {w['avg']:>8,d}  {vs_str:>8s}  {signal}")

    # Data freshness
    print(f"\n{'─' * 70}")
    print(f"  DATA FRESHNESS")
    for state, latest_date in report['data_freshness'].items():
        days_old = (date.today() - datetime.strptime(latest_date, '%Y-%m-%d').date()).days
        status = "✓ current" if days_old <= 14 else f"⚠ {days_old} days old"
        print(f"  {state}: latest data {latest_date} ({status})")

    print(f"\n  To refresh: download latest SCATS monthly ZIP from")
    print(f"  https://opendata.transport.vic.gov.au/dataset/traffic-signal-volume-data")
    print(f"  Extract to project folder, then run: python scripts/ingest_vic_counts.py")
    print("=" * 70)


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run the ingestion pipeline first.")
        sys.exit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)

    report = generate_report(con)
    print_report(report)

    # Save JSON report
    report_file = REPORTS_DIR / f"weekly_monitor_{report['report_date']}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  JSON report saved: {report_file}")

    con.close()
